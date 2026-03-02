from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.sql import Select


def _create_engine() -> Engine:
    return create_engine("duckdb:///:memory:")


def execute_statement(
    statement: Select[tuple[object, ...]], parquet_path: Path
) -> list[dict[str, object]]:
    engine = _create_engine()
    escaped_path = str(parquet_path).replace("'", "''")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE VIEW jahresbericht "
                f"AS SELECT * FROM read_parquet('{escaped_path}')"
            )
        )
        rows = connection.execute(statement).mappings().all()
    return [dict(row) for row in rows]
