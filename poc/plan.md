# Implementation Plan: Meteo Weather Chat System

A parallel PoC alongside the existing Jahresbericht system.
Two new apps: `meteo_mcp_server` (SRF Meteo API backend) + `meteo_chatbot` (web UI).
Both follow the exact same conventions, patterns, and structure as the existing apps.

---

## 1. Goal & Scope

| Dimension   | Jahresbericht system        | Meteo system (new)                |
| ----------- | --------------------------- | --------------------------------- |
| Data source | Static Parquet file (local) | Live SRF Meteo REST API           |
| MCP tools   | `query_data`, `get_catalog` | `search_location`, `get_forecast` |
| Chatbot UI  | CLI (stdin/stdout)          | Web UI (browser)                  |
| Agent       | OpenAI tool-calling         | OpenAI tool-calling (same)        |
| Transport   | Streamable HTTP             | Streamable HTTP (same)            |
| Language    | Python ≥3.14                | Python ≥3.14 (same)               |

The SRF Meteo API requires OAuth 2.0 client credentials. Credentials must be obtained from the [SRG SSR Developer Portal](https://developer.srgssr.ch). The Freemium tier provides 50 requests/day for 1 location — sufficient for a PoC.

---

## 2. Complete New File Tree

Everything created is listed below. Nothing in the existing `mcp_server/` or `chatbot/` apps is touched. Only `poc/pyproject.toml` gets minor additions.

```
poc/
├── pyproject.toml                              ← MODIFY: add new src paths
├── plan.md                                     ← this file
│
├── apps/
│   ├── mcp_server/       (existing, untouched)
│   ├── chatbot/          (existing, untouched)
│   │
│   ├── meteo_mcp_server/                       ← NEW
│   │   ├── pyproject.toml
│   │   └── src/
│   │       └── meteo_mcp_server/
│   │           ├── __init__.py
│   │           ├── main.py
│   │           ├── config.py
│   │           ├── logging.py
│   │           ├── services/
│   │           │   ├── __init__.py
│   │           │   ├── auth.py           # OAuth token lifecycle
│   │           │   └── meteo_client.py   # httpx calls to SRF Meteo API
│   │           └── tools/
│   │               ├── __init__.py
│   │               ├── search_location.py
│   │               └── get_forecast.py
│   │
│   └── meteo_chatbot/                          ← NEW
│       ├── pyproject.toml
│       └── src/
│           └── meteo_chatbot/
│               ├── __init__.py
│               └── main.py               # Gradio web chat app
│
└── docker/
    ├── mcp_server/       (existing, untouched)
    ├── chatbot/          (existing, untouched)
    ├── meteo_mcp_server/                       ← NEW
    │   └── Dockerfile
    ├── meteo_chatbot/                          ← NEW
    │   └── Dockerfile
    └── docker-compose.meteo.yml                ← NEW
```

---

## 3. SRF Meteo API — Relevant Endpoints

Base URL: `https://api.srgssr.ch/srf-meteo/v2`
Auth: OAuth 2.0 Bearer token from `https://api.srgssr.ch/oauth/v1/accesstoken?grant_type=client_credentials`

| Endpoint                         | Method | Purpose                                                   |
| -------------------------------- | ------ | --------------------------------------------------------- |
| `/geolocationNames`              | GET    | Search location by `name` or `zip`, returns list with IDs |
| `/forecastpoint/{geolocationId}` | GET    | Full forecast (daily, 3-hourly, hourly intervals)         |

The `geolocationId` format is `{lat},{lon}` rounded to 4 decimal places (e.g., `47.3769,8.5417` for Zurich).
Workflow enforced by the API: **search → get ID → get forecast**.
This mirrors the `get_catalog → query_data` workflow in the Jahresbericht system.

### Forecast Response Fields (from `/forecastpoint/{id}`)

The response has three nested arrays: `day`, `three_hours`, `one_hour`.

Key fields (daily):

| Field                | Unit     | Meaning                     |
| -------------------- | -------- | --------------------------- |
| `date_time`          | ISO-8601 | Forecast date               |
| `symbol_code`        | string   | Weather condition icon code |
| `TX_C` / `TN_C`      | °C       | Max / min temperature       |
| `PROBPCP_PERCENT`    | %        | Precipitation probability   |
| `RRR_MM`             | mm       | Rainfall amount             |
| `FF_KMH` / `FX_KMH`  | km/h     | Wind speed / gust           |
| `DD_DEG`             | degrees  | Wind direction              |
| `SUN_H`              | hours    | Sunshine duration           |
| `UVI`                | index    | UV index                    |
| `sunrise` / `sunset` | ISO-8601 | Sun times                   |

Additional fields in 3-hourly/hourly: `TTT_C` (temperature), `TTTFEEL_C` (feels-like), `RELHUM_PERCENT`, `DEWPOINT_C`, `FRESHSNOW_MM`, `PRESSURE_HPA`, `IRRADIANCE_WM2`.

---

## 4. Step-by-Step Implementation

### Step 1 — Update `poc/pyproject.toml`

Add the two new packages to the `ruff`, `pytest`, and `ty` tool configurations. The `[tool.uv.workspace] members = ["apps/*"]` glob already picks up any new directory under `apps/`, so no change is needed there.

```toml
[tool.ruff]
src = [
    "apps/chatbot/src",
    "apps/mcp_server/src",
    "apps/meteo_mcp_server/src",   # ADD
    "apps/meteo_chatbot/src",      # ADD
]

[tool.ruff.lint.isort]
known-first-party = [
    "chatbot",
    "mcp_server",
    "meteo_mcp_server",            # ADD
    "meteo_chatbot",               # ADD
]

[tool.pytest.ini_options]
pythonpath = [
    "apps/chatbot/src",
    "apps/mcp_server/src",
    "apps/meteo_mcp_server/src",   # ADD
    "apps/meteo_chatbot/src",      # ADD
]

[tool.ty.environment]
extra-paths = [
    "apps/chatbot/src",
    "apps/mcp_server/src",
    "apps/meteo_mcp_server/src",   # ADD
    "apps/meteo_chatbot/src",      # ADD
]
```

---

### Step 2 — `meteo_mcp_server`: Package Config

**`apps/meteo_mcp_server/pyproject.toml`**

Mirror `mcp_server/pyproject.toml` exactly, but replace DuckDB/SQLAlchemy with `httpx` (async HTTP client). No Parquet, no SQL needed.

```toml
[project]
name = "meteo-mcp-server"
version = "0.1.0"
description = "MCP Server for SRF Meteo API"
requires-python = ">=3.14"
dependencies = [
    "httpx>=0.28.0",
    "mcp>=1.0.0",
    "pydantic>=2.11.7",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/meteo_mcp_server"]
```

`httpx` is the async-native HTTP client — no `requests` (synchronous). It works seamlessly with `asyncio` and is the standard choice alongside FastAPI/MCP ecosystems.

---

### Step 3 — `meteo_mcp_server`: Configuration

**`apps/meteo_mcp_server/src/meteo_mcp_server/config.py`**

Mirror `mcp_server/config.py` in structure: frozen dataclass + env var loader. Add the three new API-specific fields.

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Transport = Literal["stdio", "sse", "streamable-http"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    transport: Transport
    log_level: LogLevel
    debug_enrichment: bool
    # SRF Meteo API credentials (from SRG SSR Developer Portal)
    consumer_key: str
    consumer_secret: str
    # API base URLs (rarely change; exposed for testability)
    api_base_url: str
    oauth_url: str


def load_config() -> AppConfig:
    return AppConfig(
        host=os.environ.get("MCP_SERVER_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_SERVER_PORT", "8081")),
        transport=os.environ.get("MCP_SERVER_TRANSPORT", "streamable-http"),  # type: ignore[arg-type]
        log_level=os.environ.get("MCP_SERVER_LOG_LEVEL", "INFO"),  # type: ignore[arg-type]
        debug_enrichment=os.environ.get("MCP_DEBUG_ENRICHMENT", "false").lower() == "true",
        consumer_key=os.environ["SRF_CONSUMER_KEY"],        # required — no default
        consumer_secret=os.environ["SRF_CONSUMER_SECRET"],  # required — no default
        api_base_url=os.environ.get("SRF_API_BASE_URL", "https://api.srgssr.ch/srf-meteo/v2"),
        oauth_url=os.environ.get(
            "SRF_OAUTH_URL",
            "https://api.srgssr.ch/oauth/v1/accesstoken",
        ),
    )
```

Note: `consumer_key` and `consumer_secret` use `os.environ[...]` (no default), which raises `KeyError` at startup if missing. This is intentional — fail fast on missing credentials rather than silently failing at first API call.

Environment variables:

| Variable               | Required | Default           | Purpose                                     |
| ---------------------- | -------- | ----------------- | ------------------------------------------- |
| `SRF_CONSUMER_KEY`     | **Yes**  | —                 | SRG SSR OAuth key                           |
| `SRF_CONSUMER_SECRET`  | **Yes**  | —                 | SRG SSR OAuth secret                        |
| `MCP_SERVER_HOST`      | No       | `0.0.0.0`         | Bind address                                |
| `MCP_SERVER_PORT`      | No       | `8081`            | Port (8081 to avoid conflict with existing) |
| `MCP_SERVER_TRANSPORT` | No       | `streamable-http` | MCP transport                               |
| `MCP_SERVER_LOG_LEVEL` | No       | `INFO`            | Log verbosity                               |
| `MCP_DEBUG_ENRICHMENT` | No       | `false`           | Include raw API response in debug mode      |
| `SRF_API_BASE_URL`     | No       | (production URL)  | Override for testing                        |
| `SRF_OAUTH_URL`        | No       | (production URL)  | Override for testing                        |

---

### Step 4 — `meteo_mcp_server`: Logging

**`apps/meteo_mcp_server/src/meteo_mcp_server/logging.py`**

Copy `mcp_server/logging.py` verbatim. Same structured JSON format, same `log_event()` signature. No changes needed — the pattern is domain-agnostic.

Events to emit in the meteo server:

| Event              | When                               |
| ------------------ | ---------------------------------- |
| `request_received` | Tool call arrives                  |
| `token_fetched`    | New OAuth token obtained           |
| `token_cached`     | Reused cached token                |
| `api_called`       | HTTP request sent to SRF Meteo API |
| `api_error`        | Non-2xx response from API          |
| `response_sent`    | Tool result returned               |

---

### Step 5 — `meteo_mcp_server`: Auth Service

**`apps/meteo_mcp_server/src/meteo_mcp_server/services/auth.py`**

The SRF Meteo API uses OAuth 2.0 client credentials. Tokens expire (the API returns `expires_in` seconds). The auth service handles token caching with automatic refresh.

```python
from __future__ import annotations

import base64
import time
from dataclasses import dataclass

import httpx


@dataclass
class _TokenCache:
    access_token: str
    expires_at: float  # Unix timestamp


_cache: _TokenCache | None = None
_REFRESH_BUFFER_SECONDS = 60  # refresh 60s before actual expiry


async def get_access_token(consumer_key: str, consumer_secret: str, oauth_url: str) -> str:
    """Returns a valid Bearer token, fetching a new one only when needed."""
    global _cache

    if _cache and time.time() < _cache.expires_at - _REFRESH_BUFFER_SECONDS:
        return _cache.access_token

    credentials = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            oauth_url,
            params={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {credentials}"},
        )
        response.raise_for_status()
        data = response.json()

    _cache = _TokenCache(
        access_token=data["access_token"],
        expires_at=time.time() + int(data["expires_in"]),
    )
    return _cache.access_token
```

The module-level `_cache` persists for the lifetime of the server process. For the PoC (single-process, single-worker), this is correct. If the server were multi-process, a shared cache (Redis, etc.) would be needed.

---

### Step 6 — `meteo_mcp_server`: HTTP Client Service

**`apps/meteo_mcp_server/src/meteo_mcp_server/services/meteo_client.py`**

Thin wrapper around the SRF Meteo API endpoints. Each function gets a fresh token (from cache) and makes one async HTTP call.

```python
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
    zip_code: str | None = None,
    limit: int = 5,
) -> dict[str, object]:
    """Search for Swiss locations by name or postal code."""
    params: dict[str, object] = {"limit": limit}
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
        return response.json()  # type: ignore[no-any-return]


async def fetch_forecast(
    config: AppConfig,
    geolocation_id: str,
) -> dict[str, object]:
    """Fetch full forecast data for a geolocation_id (lat,lon format)."""
    async with httpx.AsyncClient(base_url=config.api_base_url) as client:
        response = await client.get(
            f"/forecastpoint/{geolocation_id}",
            headers=await _bearer_headers(config),
        )
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]
```

---

### Step 7 — `meteo_mcp_server`: Tool Handlers

#### Tool 1: `search_location`

**`apps/meteo_mcp_server/src/meteo_mcp_server/tools/search_location.py`**

Analogous to `get_catalog`: a discovery tool the agent calls first. Returns location options with their `geolocation_id` values, which are then passed to `get_forecast`.

```python
from __future__ import annotations

from dataclasses import dataclass

from meteo_mcp_server.config import AppConfig
from meteo_mcp_server.logging import log_event
from meteo_mcp_server.services import meteo_client


@dataclass(frozen=True)
class SearchLocationContext:
    config: AppConfig


async def search_location_handler(
    context: SearchLocationContext,
    name: str | None = None,
    zip_code: str | None = None,
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
        raw = await meteo_client.search_locations(context.config, name=name, zip_code=zip_code, limit=limit)
    except Exception as exc:
        log_event("api_error", request_id=request_id, error=str(exc))
        return {"ok": False, "error": {"error_code": "API_ERROR", "message": str(exc)}}

    # Shape the response: extract id, name, lat, lon from each result
    locations = []
    for entry in raw.get("geolocationNames", []):
        geo = entry.get("geolocation", {})
        locations.append({
            "geolocation_id": f"{round(geo['latitude'], 4)},{round(geo['longitude'], 4)}",
            "name": entry.get("name", ""),
            "canton": entry.get("canton", ""),
            "latitude": geo.get("latitude"),
            "longitude": geo.get("longitude"),
        })

    log_event("response_sent", request_id=request_id, count=len(locations))
    return {"ok": True, "locations": locations, "count": len(locations)}
```

Response on success:

```json
{
  "ok": true,
  "count": 3,
  "locations": [
    { "geolocation_id": "47.3769,8.5417", "name": "Zürich", "canton": "ZH", "latitude": 47.3769, "longitude": 8.5417 },
    { "geolocation_id": "47.3523,8.5228", "name": "Zürich-Wiedikon", "canton": "ZH", ... }
  ]
}
```

#### Tool 2: `get_forecast`

**`apps/meteo_mcp_server/src/meteo_mcp_server/tools/get_forecast.py`**

Analogous to `query_data`: the main query tool. Accepts a `geolocation_id` and a `forecast_type` parameter that selects which interval to return. The full API response is filtered down to the relevant section to avoid overwhelming the LLM context window with thousands of tokens.

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from meteo_mcp_server.config import AppConfig
from meteo_mcp_server.logging import log_event
from meteo_mcp_server.services import meteo_client

ForecastType = Literal["daily", "3hourly", "hourly"]

_FORECAST_KEY = {
    "daily": "day",
    "3hourly": "three_hours",
    "hourly": "one_hour",
}

# Fields included per forecast type (controls context size returned to LLM)
_DAILY_FIELDS = {
    "date_time", "symbol_code", "TX_C", "TN_C", "PROBPCP_PERCENT",
    "RRR_MM", "FF_KMH", "FX_KMH", "DD_DEG", "SUN_H", "UVI", "sunrise", "sunset",
}
_HOURLY_FIELDS = {
    "date_time", "symbol_code", "TTT_C", "TTTFEEL_C", "PROBPCP_PERCENT",
    "RRR_MM", "FF_KMH", "DD_DEG", "RELHUM_PERCENT", "DEWPOINT_C", "PRESSURE_HPA",
}

_FIELDS_BY_TYPE: dict[ForecastType, set[str]] = {
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
    forecast_type: ForecastType = "daily",
) -> dict[str, object]:
    request_id = log_event(
        "request_received", tool="get_forecast",
        geolocation_id=geolocation_id, forecast_type=forecast_type,
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

    key = _FORECAST_KEY[forecast_type]
    intervals_raw: list[dict[str, object]] = raw.get(key, [])
    allowed_fields = _FIELDS_BY_TYPE[forecast_type]

    # Filter fields to control token usage
    intervals = [
        {k: v for k, v in interval.items() if k in allowed_fields}
        for interval in intervals_raw
    ]

    log_event("response_sent", request_id=request_id, intervals=len(intervals))
    return {
        "ok": True,
        "geolocation_id": geolocation_id,
        "forecast_type": forecast_type,
        "interval_count": len(intervals),
        "forecast": intervals,
        **({"raw_response": raw} if context.config.debug_enrichment else {}),
    }
```

---

### Step 8 — `meteo_mcp_server`: Main Entry Point

**`apps/meteo_mcp_server/src/meteo_mcp_server/main.py`**

Direct mirror of `mcp_server/main.py`. Two tools registered, context objects for dependency injection, startup validation.

```python
"""MCP server entrypoint for SRF Meteo API access."""

from mcp.server.fastmcp import FastMCP

from meteo_mcp_server.config import AppConfig, load_config
from meteo_mcp_server.tools.get_forecast import GetForecastContext, get_forecast_handler
from meteo_mcp_server.tools.search_location import SearchLocationContext, search_location_handler


def _assert_credentials(config: AppConfig) -> None:
    # consumer_key/secret already raise KeyError in load_config if missing,
    # but we can add a non-empty check here as an extra guard.
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
        zip_code: str | None = None,
        limit: int = 5,
    ) -> dict[str, object]:
        return await search_location_handler(
            context=search_ctx, name=name, zip_code=zip_code, limit=limit
        )

    @server.tool(name="get_forecast", structured_output=True)
    async def get_forecast(
        geolocation_id: str,
        forecast_type: str = "daily",
    ) -> dict[str, object]:
        return await get_forecast_handler(
            context=forecast_ctx,
            geolocation_id=geolocation_id,
            forecast_type=forecast_type,  # type: ignore[arg-type]
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
```

---

### Step 9 — `meteo_chatbot`: Package Config

**`apps/meteo_chatbot/pyproject.toml`**

Same structure as `chatbot/pyproject.toml` but adds `gradio` for the web interface.

```toml
[project]
name = "meteo-chatbot"
version = "0.1.0"
description = "Web chatbot for SRF Meteo API"
requires-python = ">=3.14"
dependencies = [
    "gradio>=5.0.0",
    "openai>=2.0.0",
    "mcp>=1.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/meteo_chatbot"]
```

**Why Gradio?**

- Pure Python — no JavaScript to write or maintain
- `gr.ChatInterface` provides a complete chat UI in ~10 lines of code
- Supports streaming responses and message history natively
- Docker-friendly (binds to `0.0.0.0:7860` by default)
- Provides a shareable temporary URL for demos (useful for thesis presentations)
- Stays close to the PoC spirit of the existing system (minimal new technology surface)

Alternative: FastAPI + HTML/JS over WebSocket. Preferred if full UI control is needed, but significantly more code for the same outcome.

---

### Step 10 — `meteo_chatbot`: Main Application

**`apps/meteo_chatbot/src/meteo_chatbot/main.py`**

The key structural difference from the CLI chatbot: Gradio manages conversation history and calls a Python `respond()` function per user turn, passing the full previous history. The MCP session is opened and closed per turn (stateless, since the meteo API has no session state).

```python
"""Web chatbot for SRF Meteo using Gradio and OpenAI tool-calling."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

SYSTEM_PROMPT = (
    "You are a weather assistant for Switzerland using live SRF Meteo data. "
    "Never invent or guess weather data — only use the provided tools. "
    "When a user mentions a location, call search_location first to resolve it to a geolocation_id. "
    "If search_location returns multiple candidates, ask the user to confirm which one. "
    "Then call get_forecast with the geolocation_id and the appropriate forecast_type "
    "('daily' for day-level overview, '3hourly' for more detail, 'hourly' for precise hourly data). "
    "In your final answer, always state the location name, the forecast date(s), and the data source."
)


# ── Utility functions (identical pattern to existing chatbot) ─────────────────

def _to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    return value


def _describe_exception(exc: BaseException) -> str:
    if isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        return _describe_exception(exc.exceptions[0])
    return str(exc) or exc.__class__.__name__


def _build_openai_tools(mcp_tools: list[Any]) -> list[dict[str, Any]]:
    specs = []
    for tool in mcp_tools:
        schema = _to_jsonable(getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None))
        specs.append({
            "type": "function",
            "function": {
                "name": str(getattr(tool, "name", "")),
                "description": str(getattr(tool, "description", "")),
                "parameters": schema or {"type": "object", "properties": {}},
            },
        })
    return specs


def _history_to_openai(history: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Convert Gradio message history to OpenAI message format."""
    messages = []
    for turn in history:
        role = turn.get("role", "")
        content = turn.get("content", "")
        if role in {"user", "assistant"}:
            messages.append({"role": role, "content": content})
    return messages


# ── Agent loop ────────────────────────────────────────────────────────────────

async def _agent_turn(
    message: str,
    history: list[dict[str, str]],
    session: Any,
    openai_client: Any,
) -> str:
    """Run one full agent turn: may involve multiple tool calls before final answer."""
    tools_result = await session.list_tools()
    tool_specs = _build_openai_tools(list(tools_result.tools))

    messages: list[dict[str, Any]] = _history_to_openai(history) + [{"role": "user", "content": message}]

    while True:
        response = openai_client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,  # deterministic tool-calling for weather data
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            tools=tool_specs,
        )

        assistant_message = response.choices[0].message
        tool_calls = assistant_message.tool_calls or []

        assistant_dict: dict[str, Any] = {
            "role": "assistant",
            "content": assistant_message.content or "",
        }
        if tool_calls:
            assistant_dict["tool_calls"] = [c.model_dump(mode="json") for c in tool_calls]
        messages.append(assistant_dict)

        if not tool_calls:
            return assistant_message.content or "[No response]"

        for call in tool_calls:
            tool_name = str(getattr(call.function, "name", ""))
            try:
                tool_input = json.loads(getattr(call.function, "arguments", "{}") or "{}")
            except json.JSONDecodeError:
                tool_input = {}

            tool_result = await session.call_tool(name=tool_name, arguments=tool_input)
            messages.append({
                "role": "tool",
                "tool_call_id": str(getattr(call, "id", "")),
                "content": json.dumps(_to_jsonable(tool_result.content), ensure_ascii=False),
            })


# ── Gradio interface ──────────────────────────────────────────────────────────

def _load_openai_client() -> Any:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Missing 'openai' dependency.") from exc
    return OpenAI(api_key=api_key)


def _make_respond_fn(openai_client: Any, mcp_server_url: str) -> Any:
    """Return an async respond() function for Gradio ChatInterface."""

    async def respond(message: str, history: list[dict[str, str]]) -> str:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            return f"Missing MCP dependency: {exc}"

        try:
            async with streamable_http_client(mcp_server_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await _agent_turn(message, history, session, openai_client)
        except Exception as exc:
            reason = _describe_exception(exc)
            return (
                f"Could not reach the MCP server at `{mcp_server_url}`. "
                f"Reason: {reason}"
            )

    return respond


def main() -> None:
    try:
        import gradio as gr
    except ImportError:
        raise SystemExit("Missing 'gradio' dependency. Run: uv sync") from None

    openai_client = _load_openai_client()
    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:8081/mcp")
    respond = _make_respond_fn(openai_client, mcp_server_url)

    demo = gr.ChatInterface(
        fn=respond,
        type="messages",
        title="SRF Meteo Chat",
        description=(
            "Ask questions about the weather in Switzerland. "
            "Powered by the SRF Meteo API and OpenAI."
        ),
        examples=[
            "What's the weather like in Zurich tomorrow?",
            "Show me the hourly forecast for Bern today.",
            "Will it rain in Geneva this week?",
            "What's the UV index in Lugano?",
        ],
        cache_examples=False,
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("GRADIO_PORT", "7860")),
    )


if __name__ == "__main__":
    main()
```

Key differences from the CLI chatbot:

| Aspect             | CLI chatbot                                 | Web chatbot                                         |
| ------------------ | ------------------------------------------- | --------------------------------------------------- |
| History management | Manual `messages` list in loop              | Gradio passes full history to each `respond()` call |
| MCP session        | One session for the entire process lifetime | New session per user turn (stateless)               |
| UI loop            | `while True` + `input()`                    | Gradio event loop (managed by framework)            |
| Temperature        | 1 (creative)                                | 0 (deterministic — weather facts must be precise)   |
| Entry point        | `asyncio.run(main())`                       | `demo.launch()` (Gradio runs its own event loop)    |

---

### Step 11 — Dockerfiles

**`poc/docker/meteo_mcp_server/Dockerfile`**

Exact mirror of `poc/docker/mcp_server/Dockerfile`. Only the package name and port change.

```dockerfile
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
COPY apps/meteo_mcp_server/ ./apps/meteo_mcp_server/

RUN uv sync --no-dev --package meteo-mcp-server

EXPOSE 8081

CMD ["uv", "run", "--package", "meteo-mcp-server", "python", "-m", "meteo_mcp_server.main"]
```

**`poc/docker/meteo_chatbot/Dockerfile`**

Mirror of `poc/docker/chatbot/Dockerfile`. Exposes 7860 (Gradio default).

```dockerfile
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
COPY apps/meteo_chatbot/ ./apps/meteo_chatbot/

RUN uv sync --no-dev --package meteo-chatbot

EXPOSE 7860

CMD ["uv", "run", "--package", "meteo-chatbot", "python", "-m", "meteo_chatbot.main"]
```

---

### Step 12 — Docker Compose

**`poc/docker/docker-compose.meteo.yml`**

A self-contained compose file for the meteo system. Can be run independently from the Jahresbericht system. Uses a `.env` file or shell environment for secrets.

```yaml
services:
  meteo-mcp-server:
    build:
      context: ../.. # Build context = poc/ (workspace root)
      dockerfile: docker/meteo_mcp_server/Dockerfile
    ports:
      - '8081:8081'
    environment:
      SRF_CONSUMER_KEY: ${SRF_CONSUMER_KEY}
      SRF_CONSUMER_SECRET: ${SRF_CONSUMER_SECRET}
      MCP_SERVER_PORT: '8081'
      MCP_SERVER_LOG_LEVEL: INFO
    healthcheck:
      test:
        [
          'CMD',
          'python',
          '-c',
          "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')",
        ]
      interval: 10s
      timeout: 5s
      retries: 3

  meteo-chatbot:
    build:
      context: ../..
      dockerfile: docker/meteo_chatbot/Dockerfile
    ports:
      - '7860:7860'
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      MCP_SERVER_URL: http://meteo-mcp-server:8081/mcp
      GRADIO_PORT: '7860'
    depends_on:
      meteo-mcp-server:
        condition: service_healthy
```

Run with:

```bash
cd poc/docker
SRF_CONSUMER_KEY=... SRF_CONSUMER_SECRET=... OPENAI_API_KEY=... docker compose -f docker-compose.meteo.yml up --build
```

Or create `poc/docker/.env`:

```
SRF_CONSUMER_KEY=your_key_here
SRF_CONSUMER_SECRET=your_secret_here
OPENAI_API_KEY=sk-...
```

---

## 5. Agent Workflow Design

The agent's tool-calling sequence for a typical user question:

```
User: "What's the weather in Bern this week?"
         │
         ▼
OpenAI sees tools: search_location, get_forecast
         │
         ▼ Tool call 1
search_location(name="Bern", limit=3)
         │
         ▼ MCP server calls /geolocationNames?name=Bern
         │
         ▼ Returns: [{geolocation_id: "46.9480,7.4474", name: "Bern", canton: "BE"}, ...]
         │
         ▼ Tool call 2
get_forecast(geolocation_id="46.9480,7.4474", forecast_type="daily")
         │
         ▼ MCP server calls /forecastpoint/46.9480,7.4474
         │
         ▼ Returns: {ok: true, forecast: [{date_time: ..., TX_C: 18, TN_C: 9, ...}, ...]}
         │
         ▼
OpenAI formulates answer: "In Bern (BE) this week: Monday 18°C/9°C with 20% rain chance..."
         │
         ▼
User sees formatted weather summary in browser
```

Disambiguation scenario (multiple locations):

```
User: "Show me the forecast for Zurich"
         │
         ▼ search_location(name="Zurich", limit=5)
         │ Returns 5 Zurich variants (Zurich city, Zurich-Airport, Zurich-Wiedikon...)
         │
         ▼ OpenAI (instructed by system prompt):
"I found several locations named Zurich. Which one do you mean?
  1. Zürich (city centre, ZH)
  2. Zürich-Flughafen (airport, ZH)
  3. Zürich-Wiedikon (district, ZH)"
         │
         ▼ User: "The city centre"
         │
         ▼ get_forecast(geolocation_id="47.3769,8.5417", forecast_type="daily")
```

---

## 6. Comparison: How This Differs from the Jahresbericht System

| Concern                | Jahresbericht system                               | Meteo system                                             |
| ---------------------- | -------------------------------------------------- | -------------------------------------------------------- |
| **Data access**        | Parquet file (static, local)                       | HTTP REST API (live, remote)                             |
| **Auth**               | None needed                                        | OAuth 2.0 client credentials                             |
| **Query language**     | Declarative template → SQL via SQLAlchemy → DuckDB | Tool parameters → HTTP GET                               |
| **Policy enforcement** | `policy.yaml` validates every query                | API itself enforces limits; no local policy layer needed |
| **Catalog**            | `catalog.yaml` + `get_catalog` tool                | Tool descriptions + `search_location` serve same purpose |
| **Validation layer**   | `validator.py` (policy check)                      | Not needed — API has own constraints                     |
| **Planner**            | SQLAlchemy SELECT builder                          | Not needed — API endpoints are the query surface         |
| **Executor**           | DuckDB                                             | `httpx` async HTTP client                                |
| **Token refresh**      | Not applicable                                     | `auth.py` with in-process cache                          |
| **Result shaping**     | `response_builder.py`                              | Field-level filtering in `get_forecast_handler`          |
| **Chatbot UI**         | CLI (`input()` loop)                               | Gradio `ChatInterface` (web browser)                     |
| **MCP session**        | One session per process                            | New session per user turn                                |
| **Temperature**        | 1                                                  | 0 (factual data warrants determinism)                    |

---

## 7. Secrets and API Access Setup

1. Register at [developer.srgssr.ch](https://developer.srgssr.ch)
2. Create an application in the portal
3. Subscribe to **SRF-MeteoProductFreemium** (free, 50 req/day, 1 location)
4. Copy the **Consumer Key** and **Consumer Secret** from the application dashboard
5. Pass them as environment variables — never commit them to the repo

Add to `.gitignore` (if not already):

```
.env
*.env.local
```

---

## 8. Implementation Order

| #   | Task                                        | Depends on                 |
| --- | ------------------------------------------- | -------------------------- |
| 1   | Update `poc/pyproject.toml`                 | —                          |
| 2   | Create `meteo_mcp_server/pyproject.toml`    | 1                          |
| 3   | Create `config.py`, `logging.py`            | 2                          |
| 4   | Create `services/auth.py`                   | 3                          |
| 5   | Create `services/meteo_client.py`           | 4                          |
| 6   | Create `tools/search_location.py`           | 5                          |
| 7   | Create `tools/get_forecast.py`              | 5                          |
| 8   | Create `meteo_mcp_server/main.py`           | 6, 7                       |
| 9   | Create `meteo_chatbot/pyproject.toml`       | 1                          |
| 10  | Create `meteo_chatbot/main.py`              | 8 (server must be running) |
| 11  | Create `docker/meteo_mcp_server/Dockerfile` | 8                          |
| 12  | Create `docker/meteo_chatbot/Dockerfile`    | 10                         |
| 13  | Create `docker/docker-compose.meteo.yml`    | 11, 12                     |
| 14  | End-to-end test via Docker Compose          | 13                         |

---

## 9. Todo List

### Phase 1 — Workspace Setup

- [x] Open `poc/pyproject.toml`
- [x] Add `apps/meteo_mcp_server/src` to `[tool.ruff] src`
- [x] Add `apps/meteo_chatbot/src` to `[tool.ruff] src`
- [x] Add `meteo_mcp_server` and `meteo_chatbot` to `[tool.ruff.lint.isort] known-first-party`
- [x] Add `apps/meteo_mcp_server/src` and `apps/meteo_chatbot/src` to `[tool.pytest.ini_options] pythonpath`
- [x] Add `apps/meteo_mcp_server/src` and `apps/meteo_chatbot/src` to `[tool.ty.environment] extra-paths`
- [x] Run `uv sync` and confirm no errors

---

### Phase 2 — `meteo_mcp_server`: Scaffold

- [x] Create directory `apps/meteo_mcp_server/src/meteo_mcp_server/`
- [x] Create directory `apps/meteo_mcp_server/src/meteo_mcp_server/services/`
- [x] Create directory `apps/meteo_mcp_server/src/meteo_mcp_server/tools/`
- [x] Create `apps/meteo_mcp_server/pyproject.toml` with deps: `httpx`, `mcp`, `pydantic`
- [x] Create `apps/meteo_mcp_server/src/meteo_mcp_server/__init__.py` (empty)
- [x] Create `apps/meteo_mcp_server/src/meteo_mcp_server/services/__init__.py` (empty)
- [x] Create `apps/meteo_mcp_server/src/meteo_mcp_server/tools/__init__.py` (empty)
- [x] Run `uv sync --package meteo-mcp-server` and confirm package resolves

---

### Phase 3 — `meteo_mcp_server`: Configuration & Logging

- [x] Create `config.py`
  - [x] Define `AppConfig` frozen dataclass with fields: `host`, `port`, `transport`, `log_level`, `debug_enrichment`, `consumer_key`, `consumer_secret`, `api_base_url`, `oauth_url`
  - [x] Implement `load_config()` reading from environment variables
  - [x] Use `os.environ[...]` (no default) for `SRF_CONSUMER_KEY` and `SRF_CONSUMER_SECRET` to fail fast at startup
  - [x] Default port to `8081` (avoids conflict with existing `mcp_server` on `8080`)
- [x] Create `logging.py`
  - [x] Copy `mcp_server/logging.py` verbatim — the `log_event()` signature is domain-agnostic and requires no changes

---

### Phase 4 — `meteo_mcp_server`: Auth Service

- [x] Create `services/auth.py`
  - [x] Define `_TokenCache` dataclass with `access_token: str` and `expires_at: float`
  - [x] Declare module-level `_cache: _TokenCache | None = None`
  - [x] Implement `get_access_token(consumer_key, consumer_secret, oauth_url) -> str`
    - [x] Return cached token if `time.time() < expires_at - 60` (60 s refresh buffer)
    - [x] Otherwise POST to OAuth URL with Basic auth (`base64(key:secret)`) and `grant_type=client_credentials`
    - [x] Parse `access_token` and `expires_in` from JSON response
    - [x] Store result in `_cache` and return token
  - [x] Call `response.raise_for_status()` so HTTP errors surface immediately

---

### Phase 5 — `meteo_mcp_server`: HTTP Client Service

- [x] Create `services/meteo_client.py`
  - [x] Implement private `_bearer_headers(config) -> dict` that calls `get_access_token` and returns `{"Authorization": "Bearer <token>"}`
  - [x] Implement `search_locations(config, name, zip_code, limit) -> dict`
    - [x] Build `params` dict from whichever of `name` / `zip` are provided
    - [x] GET `/geolocationNames` with bearer headers
    - [x] Call `response.raise_for_status()` and return `response.json()`
  - [x] Implement `fetch_forecast(config, geolocation_id) -> dict`
    - [x] GET `/forecastpoint/{geolocation_id}` with bearer headers
    - [x] Call `response.raise_for_status()` and return `response.json()`
  - [x] Use `httpx.AsyncClient(base_url=config.api_base_url)` as async context manager in both functions

---

### Phase 6 — `meteo_mcp_server`: Tool Handlers

- [x] Create `tools/search_location.py`
  - [x] Define `SearchLocationContext` frozen dataclass holding `config: AppConfig`
  - [x] Implement `search_location_handler(context, name, zip_code, limit) -> dict`
    - [x] Return `MISSING_SEARCH_TERM` error if neither `name` nor `zip_code` provided
    - [x] Call `meteo_client.search_locations()`; wrap in `try/except` returning `API_ERROR` on failure
    - [x] Shape raw API response: extract `geolocation_id` (`f"{lat:.4f},{lon:.4f}"`), `name`, `canton`, `latitude`, `longitude` per entry
    - [x] Return `{"ok": True, "locations": [...], "count": N}`
    - [x] Emit `request_received` and `response_sent` log events

- [x] Create `tools/get_forecast.py`
  - [x] Define `ForecastType = Literal["daily", "3hourly", "hourly"]`
  - [x] Define `_FORECAST_KEY` mapping forecast type → API response array key (`"day"`, `"three_hours"`, `"one_hour"`)
  - [x] Define `_DAILY_FIELDS` set: `date_time`, `symbol_code`, `TX_C`, `TN_C`, `PROBPCP_PERCENT`, `RRR_MM`, `FF_KMH`, `FX_KMH`, `DD_DEG`, `SUN_H`, `UVI`, `sunrise`, `sunset`
  - [x] Define `_HOURLY_FIELDS` set: `date_time`, `symbol_code`, `TTT_C`, `TTTFEEL_C`, `PROBPCP_PERCENT`, `RRR_MM`, `FF_KMH`, `DD_DEG`, `RELHUM_PERCENT`, `DEWPOINT_C`, `PRESSURE_HPA`
  - [x] Define `_FIELDS_BY_TYPE` mapping each `ForecastType` to its allowed field set
  - [x] Define `GetForecastContext` frozen dataclass holding `config: AppConfig`
  - [x] Implement `get_forecast_handler(context, geolocation_id, forecast_type) -> dict`
    - [x] Return `INVALID_FORECAST_TYPE` error if `forecast_type` not in `_FORECAST_KEY`
    - [x] Call `meteo_client.fetch_forecast()`; wrap in `try/except` returning `API_ERROR` on failure
    - [x] Extract interval array by `_FORECAST_KEY[forecast_type]`
    - [x] Filter each interval dict to only keys present in `_FIELDS_BY_TYPE[forecast_type]`
    - [x] Return `{"ok": True, "geolocation_id": ..., "forecast_type": ..., "interval_count": N, "forecast": [...]}`
    - [x] In debug mode (`config.debug_enrichment`): include full `raw_response`
    - [x] Emit `request_received` and `response_sent` log events

---

### Phase 7 — `meteo_mcp_server`: Entry Point

- [x] Create `main.py`
  - [x] Implement `_assert_credentials(config)`: raise `ValueError` if `consumer_key` or `consumer_secret` is empty
  - [x] Implement `_build_server(config) -> FastMCP`
    - [x] Instantiate `FastMCP` with `name="meteo-mcp-server"`, `host`, `port`, `log_level`
    - [x] Instantiate `SearchLocationContext` and `GetForecastContext` with `config`
    - [x] Register `search_location` tool via `@server.tool(name="search_location", structured_output=True)`
    - [x] Register `get_forecast` tool via `@server.tool(name="get_forecast", structured_output=True)`
    - [x] Both tool functions are `async def` delegating to their handler
  - [x] Implement `run_server(config)`: call `_assert_credentials`, build server, call `server.run(transport=config.transport)`
  - [x] Implement `main()`: call `load_config()` then `run_server()`
  - [x] Add `if __name__ == "__main__": main()` guard
- [ ] Smoke-test: `uv run --package meteo-mcp-server python -m meteo_mcp_server.main` with credentials set — confirm server starts on port 8081

---

### Phase 8 — `meteo_chatbot`: Scaffold & Package Config

- [x] Create directory `apps/meteo_chatbot/src/meteo_chatbot/`
- [x] Create `apps/meteo_chatbot/pyproject.toml` with deps: `gradio>=5.0.0`, `openai>=2.0.0`, `mcp>=1.0.0`
- [x] Create `apps/meteo_chatbot/src/meteo_chatbot/__init__.py` (empty)
- [x] Run `uv sync --package meteo-chatbot` and confirm package resolves

---

### Phase 9 — `meteo_chatbot`: Main Application

- [x] Create `main.py`
  - [x] Define `SYSTEM_PROMPT` instructing the agent to: never invent data, always call `search_location` first, confirm ambiguous locations with the user, state location + forecast dates in every answer
  - [x] Copy utility functions verbatim from `chatbot/main.py`: `_to_jsonable`, `_describe_exception`, `_build_openai_tools`
  - [x] Implement `_history_to_openai(history) -> list`: convert Gradio's `[{"role": ..., "content": ...}]` format to OpenAI message list, keeping only `user` and `assistant` roles
  - [x] Implement `_agent_turn(message, history, session, openai_client) -> str`
    - [x] Fetch tool specs from MCP session via `session.list_tools()`
    - [x] Build initial messages from `_history_to_openai(history)` + new user message
    - [x] Run inner loop: call OpenAI → if no tool calls return text; for each tool call execute via `session.call_tool()` and append tool result to messages; repeat
    - [x] Set `temperature=0` (deterministic — weather facts must not vary)
    - [x] Use `os.environ.get("OPENAI_MODEL", "gpt-4o-mini")`
  - [x] Implement `_load_openai_client()`: read `OPENAI_API_KEY` from env, raise `RuntimeError` if missing
  - [x] Implement `_make_respond_fn(openai_client, mcp_server_url) -> async fn`
    - [x] Inner `respond(message, history)` opens a fresh `streamable_http_client` + `ClientSession` per call
    - [x] Calls `_agent_turn` and returns the string result
    - [x] Catches connection errors and returns a human-readable error string (no exceptions reaching Gradio)
  - [x] Implement `main()`
    - [x] Import `gradio as gr`; raise `SystemExit` with install hint if missing
    - [x] Call `_load_openai_client()`
    - [x] Read `MCP_SERVER_URL` from env (default `http://localhost:8081/mcp`)
    - [x] Build `respond` function via `_make_respond_fn`
    - [x] Instantiate `gr.ChatInterface(fn=respond, title="SRF Meteo Chat", examples=[...], cache_examples=False)`
    - [x] Call `demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("GRADIO_PORT", "7860")))`
  - [x] Add `if __name__ == "__main__": main()` guard
- [ ] Smoke-test: start `meteo_mcp_server` locally, then `uv run --package meteo-chatbot python -m meteo_chatbot.main` — confirm Gradio UI opens in browser and a test query returns a weather response

---

### Phase 10 — Docker

- [x] Create `poc/docker/meteo_mcp_server/Dockerfile`
  - [x] Base image: `python:3.14-slim`
  - [x] Copy `uv` from `ghcr.io/astral-sh/uv:latest`
  - [x] `WORKDIR /app`
  - [x] `COPY pyproject.toml uv.lock* README.md ./`
  - [x] `COPY apps/meteo_mcp_server/ ./apps/meteo_mcp_server/`
  - [x] `RUN uv sync --no-dev --package meteo-mcp-server`
  - [x] `EXPOSE 8081`
  - [x] `CMD ["uv", "run", "--package", "meteo-mcp-server", "python", "-m", "meteo_mcp_server.main"]`
- [x] Create `poc/docker/meteo_chatbot/Dockerfile`
  - [x] Base image: `python:3.14-slim`
  - [x] Copy `uv` from `ghcr.io/astral-sh/uv:latest`
  - [x] `WORKDIR /app`
  - [x] `COPY pyproject.toml uv.lock* README.md ./`
  - [x] `COPY apps/meteo_chatbot/ ./apps/meteo_chatbot/`
  - [x] `RUN uv sync --no-dev --package meteo-chatbot`
  - [x] `EXPOSE 7860`
  - [x] `CMD ["uv", "run", "--package", "meteo-chatbot", "python", "-m", "meteo_chatbot.main"]`
- [x] Create `poc/docker/docker-compose.meteo.yml`
  - [x] Service `meteo-mcp-server`: build from `docker/meteo_mcp_server/Dockerfile`, context `../..`, port `8081:8081`, env vars `SRF_CONSUMER_KEY`, `SRF_CONSUMER_SECRET`, `MCP_SERVER_PORT=8081`, healthcheck on `/health`
  - [x] Service `meteo-chatbot`: build from `docker/meteo_chatbot/Dockerfile`, context `../..`, port `7860:7860`, env vars `OPENAI_API_KEY`, `MCP_SERVER_URL=http://meteo-mcp-server:8081/mcp`, `GRADIO_PORT=7860`, `depends_on: meteo-mcp-server (service_healthy)`
- [x] Create `poc/docker/.env.example` with placeholder values for `SRF_CONSUMER_KEY`, `SRF_CONSUMER_SECRET`, `OPENAI_API_KEY`
- [x] Confirm `poc/docker/.env` is listed in `.gitignore`

---

### Phase 11 — End-to-End Verification

- [x] Build images: `docker compose -f docker-compose.meteo.yml build`
- [x] Start stack: `docker compose -f docker-compose.meteo.yml up`
- [ ] Confirm `meteo-mcp-server` container starts and passes healthcheck
- [ ] Confirm `meteo-chatbot` container starts after server is healthy
- [ ] Open `http://localhost:7860` in browser — confirm Gradio UI loads
- [ ] Send test query: _"What's the weather in Zurich tomorrow?"_ — confirm agent calls `search_location` then `get_forecast` and returns a coherent answer
- [ ] Send ambiguous query: _"Show me the forecast for Zurich"_ — confirm agent lists candidates and asks for clarification
- [ ] Confirm Docker logs show structured JSON events from the MCP server
- [ ] Shut down: `docker compose -f docker-compose.meteo.yml down`
