"""MCP server entrypoint for constrained Jahresbericht data access."""

from mcp.server.fastmcp import FastMCP

from mcp_server.config import AppConfig, load_config
from mcp_server.contracts.models import FilterModel, MetricModel, SortModel
from mcp_server.tools.get_catalog import CatalogContext, get_catalog_handler
from mcp_server.tools.query_data import QueryDataContext, query_data_handler


def _assert_required_files(config: AppConfig) -> None:
    required_paths = [
        config.contracts_dir / "query_template.schema.json",
        config.contracts_dir / "policy.yaml",
        config.contracts_dir / "catalog.yaml",
        config.data_parquet_path,
    ]
    missing_paths = [path for path in required_paths if not path.exists()]
    if missing_paths:
        missing_display = ", ".join(str(path) for path in missing_paths)
        raise FileNotFoundError(f"Missing required runtime artifacts: {missing_display}")


def _build_server(config: AppConfig) -> FastMCP:
    server = FastMCP(
        name="jahresbericht-mcp-server",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
    )

    query_context = QueryDataContext(config=config)
    catalog_context = CatalogContext(config=config)

    @server.tool(
        name="query_data",
        description=(
            "Execute a validated, read-only query on the Mediapulse TV Jahresbericht dataset. "
            "Required: at least one entry in metrics and exactly one Region eq-filter. "
            "Call get_catalog first whenever you are unsure of exact filter values "
            "(Region codes, Sender names, Metrik values). "
            "Do NOT guess filter values — use only values confirmed by get_catalog."
        ),
    )
    def query_data(
        metrics: list[MetricModel],
        filters: list[FilterModel],
        group_by: list[str],
        sort: list[SortModel],
        limit: int | None = None,
    ) -> dict[str, object]:
        raw_template: dict[str, object] = {
            "metrics": [m.model_dump() for m in metrics],
            "filters": [f.model_dump() for f in filters],
            "group_by": group_by,
            "sort": [s.model_dump() for s in sort],
            "limit": limit,
        }
        return query_data_handler(template=raw_template, context=query_context)

    @server.tool(
        name="get_catalog",
        description=(
            "Return catalog metadata: "
            "allowed column values, metric definitions, and timeslot options. "
            "Call this BEFORE query_data when you are not certain of exact filter values. "
            "Pass a search term to look up a specific column or metric by name or German alias. "
            "Omit the term to receive the full catalog. "
            "If the response contains selection_required=true, show the candidates to the user. "
            "If selection_required=false or absent, use the returned values directly in query_data."
        ),
    )
    def get_catalog(term: str | None = None) -> dict[str, object]:
        return get_catalog_handler(context=catalog_context, term=term)

    return server


def run_server(config: AppConfig) -> None:
    _assert_required_files(config)
    server = _build_server(config)
    server.run(transport=config.transport)


def main() -> None:
    config = load_config()
    run_server(config=config)


if __name__ == "__main__":
    main()
