from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from meteo_mcp_server.config import AppConfig, load_config
from meteo_mcp_server.tools.get_forecast import GetForecastContext, get_forecast_handler
from meteo_mcp_server.tools.search_location import SearchLocationContext, search_location_handler


def _assert_credentials(config: AppConfig) -> None:
    if not config.consumer_key or not config.consumer_secret:
        raise ValueError("SRF_CONSUMER_KEY and SRF_CONSUMER_SECRET must not be empty.")


def _build_server(config: AppConfig) -> FastMCP:
    server = FastMCP(
        name="meteo-mcp-server",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
    )

    search_ctx = SearchLocationContext(config=config)
    forecast_ctx = GetForecastContext(config=config)

    @server.tool(name="search_location", structured_output=True)
    async def search_location(
        name: str | None = None,
        zip_code: int | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        """Search for Swiss locations by name or postal code.
        Returns a list of matches with geolocation_id, name, canton, latitude, and longitude.
        Always call this first to resolve a place name before calling get_forecast."""
        return await search_location_handler(
            context=search_ctx, name=name, zip_code=zip_code, limit=limit
        )

    @server.tool(name="get_forecast", structured_output=True)
    async def get_forecast(
        geolocation_id: str,
        forecast_type: str = "daily",
    ) -> dict[str, object]:
        """Fetch weather forecast for a location.
        geolocation_id: the value from a search_location result (format: 'lat,lon').
        forecast_type: 'daily' for a 7-day overview, '3hourly' for 3-hour intervals,
        or 'hourly' for hour-by-hour data."""
        return await get_forecast_handler(
            context=forecast_ctx,
            geolocation_id=geolocation_id,
            forecast_type=forecast_type,
        )

    return server


def run_server(config: AppConfig) -> None:
    _assert_credentials(config)
    server = _build_server(config)
    server.run(transport=config.transport)


def main() -> None:
    config = load_config()
    run_server(config=config)


if __name__ == "__main__":
    main()
