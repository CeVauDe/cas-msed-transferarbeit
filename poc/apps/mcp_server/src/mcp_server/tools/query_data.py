from __future__ import annotations

from dataclasses import dataclass

from mcp_server.config import AppConfig
from mcp_server.logging import log_event
from mcp_server.services.executor_duckdb import execute_statement
from mcp_server.services.loaders import load_policy
from mcp_server.services.planner import build_query_plan, build_runtime_table
from mcp_server.services.response_builder import build_response
from mcp_server.services.validator import validate_template


@dataclass(frozen=True)
class QueryDataContext:
    config: AppConfig


def query_data_handler(template: dict[str, object], context: QueryDataContext) -> dict[str, object]:
    request_id = log_event("request_received", tool="query_data")

    policy_path = context.config.contracts_dir / "policy.yaml"
    policy = load_policy(policy_path)

    validation = validate_template(raw_template=template, policy=policy)
    if not validation.valid or validation.template is None:
        log_event("validation_failed", request_id=request_id, error=validation.error)
        return {"ok": False, "error": validation.error, "request_id": request_id}

    log_event("validated", request_id=request_id)
    runtime_table = build_runtime_table(policy)
    query_plan = build_query_plan(template=validation.template, table_model=runtime_table)

    log_event("planned", request_id=request_id)
    try:
        rows = execute_statement(
            statement=query_plan.statement,
            parquet_path=context.config.data_parquet_path,
        )
    except Exception as exc:
        log_event("error", request_id=request_id, error_code="EXECUTION_ERROR", error=str(exc))
        return {
            "ok": False,
            "request_id": request_id,
            "error": {
                "error_code": "EXECUTION_ERROR",
                "message": "Execution failed for validated query template.",
                "details": {"reason": str(exc)},
            },
        }

    log_event("executed", request_id=request_id, row_count=len(rows))

    payload = build_response(
        rows=rows,
        template=validation.template,
        debug_enrichment=context.config.debug_enrichment,
        template_version=policy.version,
    )
    log_event("response_sent", request_id=request_id, row_count=len(rows))
    return {"ok": True, "request_id": request_id, "result": payload}
