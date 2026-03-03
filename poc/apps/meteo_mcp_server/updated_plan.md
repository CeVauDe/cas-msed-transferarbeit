# meteo_mcp_server — Spec Verification & Update Plan

Cross-reference of all `meteo_mcp_server` source files against
`SRFWeather-OpenApi3.yaml` (v2.0.1). Issues are ordered by severity.

---

## 1. Wrong return type on `search_locations` (bug / misleading)

**File:** `services/meteo_client.py:19`

```python
# current
async def search_locations(...) -> dict[str, object]:

# proposed
async def search_locations(...) -> object:
```

**Why:** The spec declares the `/geolocationNames` response as a single
`geolocationNames_search` object, but the real API returns a **bare list**
of those objects (confirmed from runtime logs). The current `dict[str, object]`
annotation is wrong in both directions: the spec object is a dict, but reality
is a list. Using `object` is the honest annotation and matches what
`search_location_handler` already defends against with `isinstance(raw, list)`.

---

## 2. `_HOURLY_FIELDS` missing `FX_KMH` (data loss)

**File:** `tools/get_forecast.py:23-26`

```python
# current
_HOURLY_FIELDS: frozenset[str] = frozenset({
    "date_time", "symbol_code", "TTT_C", "TTTFEEL_C", "PROBPCP_PERCENT",
    "RRR_MM", "FF_KMH", "DD_DEG", "RELHUM_PERCENT", "DEWPOINT_C", "PRESSURE_HPA",
})

# proposed — add FX_KMH and SUN_MIN
_HOURLY_FIELDS: frozenset[str] = frozenset({
    "date_time", "symbol_code", "TTT_C", "TTTFEEL_C", "PROBPCP_PERCENT",
    "RRR_MM", "FF_KMH", "FX_KMH", "DD_DEG", "SUN_MIN",
    "RELHUM_PERCENT", "DEWPOINT_C", "PRESSURE_HPA",
})
```

**Why:** The spec marks `FX_KMH` (gust speed in km/h) as a **required** field
in both `ThreeHourForecastInterval` and `OneHourForecastInterval`. It is present
in `_DAILY_FIELDS` but was accidentally omitted from `_HOURLY_FIELDS`, so
3-hourly and hourly gust data is silently filtered out. `SUN_MIN` (sunshine
duration in minutes for the interval) is also in the spec and adds meaningful
context for hourly forecasts.

---

## 3. Stale diagnostic logging leaks into production (noise / correctness)

**File:** `tools/get_forecast.py:67-73`

```python
# current — always logs large repr string
log_event(
    "api_response",
    request_id=request_id,
    raw_type=type(raw).__name__,
    raw_keys=list(raw.keys()) if isinstance(raw, dict) else None,
    raw_repr=repr(raw)[:800],   # ← 800-char raw dump every request
)
```

**Proposed:** Remove the `log_event("api_response", ...)` call entirely now
that the response structure is understood and handled. The `api_response` event
was added only as a one-shot diagnostic. Keeping it permanently produces ~800
bytes of log noise on every forecast request. If future debugging is needed,
the `debug_enrichment` flag already gates `raw_response` in the result payload.

---

## 4. Tool functions have no descriptions (LLM usability)

**File:** `main.py:26-45`

```python
# current — no docstrings, FastMCP will expose empty descriptions
@server.tool(name="search_location", structured_output=True)
async def search_location(name: str | None = None, ...):
    return await search_location_handler(...)

@server.tool(name="get_forecast", structured_output=True)
async def get_forecast(geolocation_id: str, ...):
    return await get_forecast_handler(...)
```

**Proposed:** Add docstrings to both inner tool functions. FastMCP uses the
function's docstring as the tool description sent to the LLM. Without it the
LLM has no guidance on when or how to call the tools, degrading reliability.

Example:
```python
@server.tool(name="search_location", structured_output=True)
async def search_location(name: str | None = None, zip_code: str | None = None, limit: int = 5) -> dict[str, object]:
    """Search for Swiss locations by name or postal code.
    Returns a list of matches with geolocation_id, name, canton, lat, lon.
    Call this first to resolve a place name before calling get_forecast."""
    return await search_location_handler(...)

@server.tool(name="get_forecast", structured_output=True)
async def get_forecast(geolocation_id: str, forecast_type: str = "daily") -> dict[str, object]:
    """Fetch weather forecast for a location.
    geolocation_id: value from search_location result (format: 'lat,lon').
    forecast_type: 'daily' (7-day overview), '3hourly', or 'hourly'."""
    return await get_forecast_handler(...)
```

---

## 5. `zip_code` parameter type inconsistency (minor / spec deviation)

**File:** `tools/search_location.py:18`, `services/meteo_client.py:17`

The spec declares the `zip` query parameter as `integer (int32)`. The tool
exposes `zip_code: str | None` and sends the raw string to the API. httpx
serialises it identically (`?zip=8001`), so it works in practice, but:

- The tool schema advertises `string` for zip, while the API expects an integer.
- An LLM could pass `"01"` (leading zero), which the API may reject.

**Proposed:** Change `zip_code` to `int | None` in both the tool signature and
the client, so the MCP tool schema correctly advertises `integer` and leading
zeros are impossible.

---

## 6. `name` variable shadows function parameter (code smell)

**File:** `tools/search_location.py:70`

```python
async def search_location_handler(
    context: SearchLocationContext,
    name: str | None = None,   # ← parameter
    ...
):
    ...
    for _entry in raw_entries:
        ...
        name = str(geo.get("default_name") or entry.get("name") or "")  # ← shadows parameter
```

After line 70, the function parameter `name` is permanently overwritten in the
loop. This works today because `name` is only needed before the loop (in the
`log_event` and `search_locations` calls), but it is fragile. Rename the local
variable to `location_name` or `display_name`.

---

## Summary table

| # | File | Severity | Change |
|---|------|----------|--------|
| 1 | `services/meteo_client.py:19` | Medium | Fix `search_locations` return type annotation to `object` |
| 2 | `tools/get_forecast.py:23` | Medium | Add `FX_KMH`, `SUN_MIN` to `_HOURLY_FIELDS` |
| 3 | `tools/get_forecast.py:67` | Low | Remove stale `api_response` diagnostic log event |
| 4 | `main.py:26,36` | Low | Add docstrings to tool functions for LLM descriptions |
| 5 | `tools/search_location.py:18` | Low | Change `zip_code: str` → `zip_code: int` |
| 6 | `tools/search_location.py:70` | Low | Rename local `name` → `location_name` to avoid shadowing |

No structural changes required — the core architecture, response envelopes,
field allowlists for daily forecasts, auth flow, and MCP tool wiring are all
correct and match the spec.
