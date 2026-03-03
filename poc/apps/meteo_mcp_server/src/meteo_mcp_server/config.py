from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast

Transport = Literal["stdio", "sse", "streamable-http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    transport: Transport
    log_level: LogLevel
    debug_enrichment: bool
    consumer_key: str
    consumer_secret: str
    api_base_url: str
    oauth_url: str


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    transport_raw = os.environ.get("MCP_SERVER_TRANSPORT", "streamable-http")
    if transport_raw not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Invalid MCP transport: {transport_raw}")
    transport = cast(Transport, transport_raw)

    log_level_raw = os.environ.get("MCP_SERVER_LOG_LEVEL", "INFO")
    if log_level_raw not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Invalid log level: {log_level_raw}")
    log_level = cast(LogLevel, log_level_raw)

    return AppConfig(
        host=os.environ.get("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_SERVER_PORT", "8081")),
        transport=transport,
        log_level=log_level,
        debug_enrichment=_parse_bool(os.environ.get("MCP_DEBUG_ENRICHMENT"), default=False),
        consumer_key=os.environ["SRF_CONSUMER_KEY"],
        consumer_secret=os.environ["SRF_CONSUMER_SECRET"],
        api_base_url=os.environ.get("SRF_API_BASE_URL", "https://api.srgssr.ch/srf-meteo/v2"),
        oauth_url=os.environ.get(
            "SRF_OAUTH_URL",
            "https://api.srgssr.ch/oauth/v1/accesstoken",
        ),
    )
