from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from mcp_server.config import AppConfig
from mcp_server.logging import get_logger
from mcp_server.services.executor_duckdb import execute_statement
from mcp_server.services.loaders import load_policy
from mcp_server.services.planner import build_query_plan, build_runtime_table
from mcp_server.services.response_builder import build_response
from mcp_server.services.validator import validate_template

log = get_logger(__name__)


@dataclass(frozen=True)
class QueryDataContext:
    config: AppConfig


def query_data_handler(template: dict[str, object], context: QueryDataContext) -> dict[str, object]:
    request_id = str(uuid4())

    log.debug(
        "query_data request received:\n%s",
        json.dumps(template, indent=2, ensure_ascii=False),
    )

    policy_path = context.config.contracts_dir / "policy.yaml"
    policy = load_policy(policy_path)

    validation = validate_template(raw_template=template, policy=policy)
    if not validation.valid or validation.template is None:
        log.error("Validation failed: %s", validation.error)
        return {"ok": False, "error": validation.error, "request_id": request_id}

    log.info("Template validated")
    runtime_table = build_runtime_table(policy)
    query_plan = build_query_plan(template=validation.template, table_model=runtime_table)

    log.debug("Query planned: %s", query_plan.statement)
    try:
        rows = execute_statement(
            statement=query_plan.statement,
            parquet_path=context.config.data_parquet_path,
        )
    except Exception as exc:
        log.error("Execution error: %s", exc)
        return {
            "ok": False,
            "request_id": request_id,
            "error": {
                "error_code": "EXECUTION_ERROR",
                "message": "Execution failed for validated query template.",
                "details": {"reason": str(exc)},
            },
        }

    log.info("Query executed, row_count=%d", len(rows))

    payload = build_response(
        rows=rows,
        template=validation.template,
        debug_enrichment=context.config.debug_enrichment,
        template_version=policy.version,
    )
    preview_rows = rows[:5]
    log.debug(
        "Response sent, row_count=%d, preview:\n%s",
        len(rows),
        json.dumps(preview_rows, indent=2, ensure_ascii=False, default=str),
    )
    return {"ok": True, "request_id": request_id, "result": payload}
