from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from meteo_mcp_server.config import AppConfig
from meteo_mcp_server.logging import log_event
from meteo_mcp_server.services import meteo_client


@dataclass(frozen=True)
class SearchLocationContext:
    config: AppConfig


async def search_location_handler(
    context: SearchLocationContext,
    name: str | None = None,
    zip_code: int | None = None,
    limit: int = 5,
) -> dict[str, object]:
    request_id = log_event("request_received", tool="search_location", name=name, zip=zip_code)

    if not name and not zip_code:
        return {
            "ok": False,
            "error": {
                "error_code": "MISSING_SEARCH_TERM",
                "message": "Provide at least one of: name, zip_code.",
            },
        }

    try:
        raw = await meteo_client.search_locations(
            context.config, name=name, zip_code=zip_code, limit=limit
        )
    except Exception as exc:
        log_event("api_error", request_id=request_id, error=str(exc))
        return {"ok": False, "error": {"error_code": "API_ERROR", "message": str(exc)}}

    locations: list[dict[str, object]] = []

    # SRF API returns a bare list; older versions wrapped it in {"geolocationNames": [...]}
    if isinstance(raw, list):
        raw_entries = raw
    elif isinstance(raw, dict):
        raw_list: object = cast(dict[str, object], raw).get("geolocationNames")
        raw_entries = raw_list if isinstance(raw_list, list) else []
    else:
        log_event(
            "parse_error",
            request_id=request_id,
            reason="unexpected_raw_type",
            raw_type=type(raw).__name__,
        )
        return {"ok": True, "locations": [], "count": 0}

    for _entry in raw_entries:
        if not isinstance(_entry, dict):
            continue
        entry = cast(dict[str, object], _entry)

        geo_nested = entry.get("geolocation")
        geo: dict[str, object] = (
            cast(dict[str, object], geo_nested) if isinstance(geo_nested, dict) else {}
        )

        # SRF API uses lat/lon inside the geolocation object
        lat: object = (
            geo.get("lat") or geo.get("latitude") or entry.get("lat") or entry.get("latitude")
        )
        lon: object = (
            geo.get("lon") or geo.get("longitude") or entry.get("lon") or entry.get("longitude")
        )

        if not isinstance(lat, float | int) or not isinstance(lon, float | int):
            log_event(
                "parse_skip",
                request_id=request_id,
                entry_keys=list(entry.keys()),
                geo_keys=list(geo.keys()),
            )
            continue

        # Name: prefer default_name from geolocation, fall back to top-level name
        location_name = str(geo.get("default_name") or entry.get("name") or "")

        # Canton: extract province from the first geolocation_names entry
        canton = ""
        geo_names_raw = geo.get("geolocation_names")
        if isinstance(geo_names_raw, list) and geo_names_raw:
            first_geo_name = geo_names_raw[0]
            if isinstance(first_geo_name, dict):
                canton = str(cast(dict[str, object], first_geo_name).get("province") or "")

        locations.append(
            {
                "geolocation_id": f"{float(lat):.4f},{float(lon):.4f}",
                "name": location_name,
                "canton": canton,
                "latitude": lat,
                "longitude": lon,
            }
        )

    log_event("response_sent", request_id=request_id, count=len(locations))
    return {"ok": True, "locations": locations, "count": len(locations)}
