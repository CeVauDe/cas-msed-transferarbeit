from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from meteo_mcp_server.config import AppConfig
from meteo_mcp_server.logging import log_event
from meteo_mcp_server.services import meteo_client

ForecastType = Literal["daily", "3hourly", "hourly"]

_FORECAST_KEY: dict[str, str] = {
    "daily": "days",
    "3hourly": "three_hours",
    "hourly": "hours",
}

_DAILY_FIELDS: frozenset[str] = frozenset(
    {
        "date_time",
        "symbol_code",
        "TX_C",
        "TN_C",
        "PROBPCP_PERCENT",
        "RRR_MM",
        "FF_KMH",
        "FX_KMH",
        "DD_DEG",
        "SUN_H",
        "UVI",
        "SUNRISE",
        "SUNSET",
    }
)

_HOURLY_FIELDS: frozenset[str] = frozenset(
    {
        "date_time",
        "symbol_code",
        "TTT_C",
        "TTTFEEL_C",
        "PROBPCP_PERCENT",
        "RRR_MM",
        "FF_KMH",
        "FX_KMH",
        "DD_DEG",
        "SUN_MIN",
        "RELHUM_PERCENT",
        "DEWPOINT_C",
        "PRESSURE_HPA",
    }
)

_FIELDS_BY_TYPE: dict[str, frozenset[str]] = {
    "daily": _DAILY_FIELDS,
    "3hourly": _HOURLY_FIELDS,
    "hourly": _HOURLY_FIELDS,
}


@dataclass(frozen=True)
class GetForecastContext:
    config: AppConfig


async def get_forecast_handler(
    context: GetForecastContext,
    geolocation_id: str,
    forecast_type: str = "daily",
) -> dict[str, object]:
    request_id = log_event(
        "request_received",
        tool="get_forecast",
        geolocation_id=geolocation_id,
        forecast_type=forecast_type,
    )

    if forecast_type not in _FORECAST_KEY:
        return {
            "ok": False,
            "error": {
                "error_code": "INVALID_FORECAST_TYPE",
                "message": f"forecast_type must be one of: {list(_FORECAST_KEY)}",
            },
        }

    try:
        raw = await meteo_client.fetch_forecast(context.config, geolocation_id)
    except Exception as exc:
        log_event("api_error", request_id=request_id, error=str(exc))
        return {"ok": False, "error": {"error_code": "API_ERROR", "message": str(exc)}}

    if not isinstance(raw, dict):
        log_event(
            "parse_error", request_id=request_id, reason="raw_not_dict", raw_type=type(raw).__name__
        )
        return {
            "ok": True,
            "geolocation_id": geolocation_id,
            "forecast_type": forecast_type,
            "interval_count": 0,
            "forecast": [],
        }

    key = _FORECAST_KEY[forecast_type]
    raw_intervals = raw.get(key)
    allowed_fields = _FIELDS_BY_TYPE[forecast_type]

    intervals: list[dict[str, object]] = []
    if isinstance(raw_intervals, list):
        for item in raw_intervals:
            if isinstance(item, dict):
                intervals.append({str(k): v for k, v in item.items() if str(k) in allowed_fields})

    log_event("response_sent", request_id=request_id, intervals=len(intervals))

    result: dict[str, object] = {
        "ok": True,
        "geolocation_id": geolocation_id,
        "forecast_type": forecast_type,
        "interval_count": len(intervals),
        "forecast": intervals,
    }
    if context.config.debug_enrichment:
        result["raw_response"] = raw
    return result
