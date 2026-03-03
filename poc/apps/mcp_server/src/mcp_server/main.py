"""MCP server entrypoint for constrained Jahresbericht data access."""

from mcp.server.fastmcp import FastMCP

from mcp_server.config import AppConfig, load_config
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

    @server.tool(name="query_data", structured_output=True)
    def query_data(template: dict[str, object]) -> dict[str, object]:
        return query_data_handler(template=template, context=query_context)

    @server.tool(name="get_catalog", structured_output=True)
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
