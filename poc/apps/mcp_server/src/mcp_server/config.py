from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

Transport = Literal["stdio", "sse", "streamable-http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    transport: Transport
    data_parquet_path: Path
    contracts_dir: Path
    debug_enrichment: bool
    log_level: LogLevel


def _parse_bool(raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> AppConfig:
    package_root = Path(__file__).resolve().parent
    app_root = package_root.parent.parent

    contracts_dir = app_root / "src" / "mcp_server" / "contracts"
    data_default = app_root / "data" / "Jahresbericht_all.parquet"

    host = os.environ.get("MCP_SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_SERVER_PORT", "8080"))
    transport_raw = os.environ.get("MCP_SERVER_TRANSPORT", "streamable-http")
    if transport_raw not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Invalid MCP transport: {transport_raw}")
    transport = cast(Transport, transport_raw)

    log_level_raw = os.environ.get("MCP_SERVER_LOG_LEVEL", "INFO")
    if log_level_raw not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Invalid log level: {log_level_raw}")
    log_level = cast(LogLevel, log_level_raw)
    debug_enrichment = _parse_bool(os.environ.get("MCP_DEBUG_ENRICHMENT"), default=False)
    data_path_raw = os.environ.get("MCP_DATA_PARQUET_PATH")
    data_parquet_path = Path(data_path_raw) if data_path_raw else data_default

    return AppConfig(
        host=host,
        port=port,
        transport=transport,
        data_parquet_path=data_parquet_path,
        contracts_dir=contracts_dir,
        debug_enrichment=debug_enrichment,
        log_level=log_level,
    )
