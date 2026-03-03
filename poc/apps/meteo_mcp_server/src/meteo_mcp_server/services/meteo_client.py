from __future__ import annotations

import httpx

from meteo_mcp_server.config import AppConfig
from meteo_mcp_server.services.auth import get_access_token


async def _bearer_headers(config: AppConfig) -> dict[str, str]:
    token = await get_access_token(config.consumer_key, config.consumer_secret, config.oauth_url)
    return {"Authorization": f"Bearer {token}"}


async def search_locations(
    config: AppConfig,
    name: str | None = None,
    zip_code: int | None = None,
    limit: int = 5,
) -> object:
    params: dict[str, str | int] = {"limit": limit}
    if name:
        params["name"] = name
    if zip_code:
        params["zip"] = zip_code

    async with httpx.AsyncClient(base_url=config.api_base_url) as client:
        response = await client.get(
            "/geolocationNames",
            params=params,
            headers=await _bearer_headers(config),
        )
        response.raise_for_status()
        return response.json()


async def fetch_forecast(
    config: AppConfig,
    geolocation_id: str,
) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=config.api_base_url) as client:
        response = await client.get(
            f"/forecastpoint/{geolocation_id}",
            headers=await _bearer_headers(config),
        )
        response.raise_for_status()
        return response.json()
