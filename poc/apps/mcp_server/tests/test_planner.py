from pathlib import Path

from sqlalchemy import create_engine, text

from mcp_server.services.loaders import load_policy
from mcp_server.services.planner import build_query_plan, build_runtime_table
from mcp_server.services.validator import validate_template


def test_planner_builds_statement_and_runs_on_duckdb() -> None:
    policy_path = (
        Path(__file__).resolve().parents[1] / "src" / "mcp_server" / "contracts" / "policy.yaml"
    )
    policy = load_policy(policy_path)

    template: dict[str, object] = {
        "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
        "filters": [{"column": "Region", "op": "eq", "value": "DS"}],
        "group_by": ["Sender"],
        "sort": [{"column": "wert_sum", "direction": "desc"}],
        "limit": 5,
    }

    validation = validate_template(raw_template=template, policy=policy)
    assert validation.valid is True
    assert validation.template is not None

    runtime_table = build_runtime_table(policy)
    plan = build_query_plan(template=validation.template, table_model=runtime_table)

    parquet_path = Path(__file__).resolve().parents[1] / "data" / "Jahresbericht_all.parquet"
    escaped_path = str(parquet_path).replace("'", "''")
    engine = create_engine("duckdb:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(f"CREATE VIEW jahresbericht AS SELECT * FROM read_parquet('{escaped_path}')")
        )
        rows = connection.execute(plan.statement).mappings().all()

    assert len(rows) <= 5
