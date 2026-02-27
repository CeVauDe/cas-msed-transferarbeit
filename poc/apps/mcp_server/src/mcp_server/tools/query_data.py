from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from mcp_server.config import AppConfig
from mcp_server.logging import bind_request_context, get_logger
from mcp_server.services.executor_duckdb import execute_statement
from mcp_server.services.loaders import load_policy
from mcp_server.services.planner import build_query_plan, build_runtime_table
from mcp_server.services.response_builder import build_response
from mcp_server.services.validator import validate_template


@dataclass(frozen=True)
class QueryDataContext:
    config: AppConfig


def query_data_handler(template: dict[str, object], context: QueryDataContext) -> dict[str, object]:
    # Initialize logger and bind request context
    request_id = str(uuid4())
    log = get_logger(__name__)
    log = bind_request_context(log, request_id=request_id)

    log.info("request_received", tool="query_data")

    policy_path = context.config.contracts_dir / "policy.yaml"
    policy = load_policy(policy_path)

    validation = validate_template(raw_template=template, policy=policy)
    if not validation.valid or validation.template is None:
        log.error("validation_failed", error=validation.error)
        return {"ok": False, "error": validation.error, "request_id": request_id}

    log.info("validated")
    runtime_table = build_runtime_table(policy)
    query_plan = build_query_plan(template=validation.template, table_model=runtime_table)

    log.debug("planned", statement=query_plan.statement)
    try:
        rows = execute_statement(
            statement=query_plan.statement,
            parquet_path=context.config.data_parquet_path,
        )
    except Exception as exc:
        log.error("execution_error", error_code="EXECUTION_ERROR", error=str(exc))
        return {
            "ok": False,
            "request_id": request_id,
            "error": {
                "error_code": "EXECUTION_ERROR",
                "message": "Execution failed for validated query template.",
                "details": {"reason": str(exc)},
            },
        }

    log.info("executed", row_count=len(rows))

    payload = build_response(
        rows=rows,
        template=validation.template,
        debug_enrichment=context.config.debug_enrichment,
        template_version=policy.version,
    )
    log.info("response_sent", row_count=len(rows))
    return {"ok": True, "request_id": request_id, "result": payload}
