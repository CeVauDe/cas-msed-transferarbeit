# Research Report: `poc/apps/` — Deep Dive

> Analysis of the two applications in `poc/apps/`: `mcp_server` and `chatbot`.
> These form a proof-of-concept AI data assistant system for SRF/SRG Jahresbericht analytics.

---

## 1. Overview

The system has two components that work together:

| App          | Role                                 | Protocol                            |
| ------------ | ------------------------------------ | ----------------------------------- |
| `mcp_server` | Policy-controlled data query backend | MCP (Model Context Protocol) server |
| `chatbot`    | Gradio web chatbot                   | MCP client + OpenAI tool-calling    |

The architecture separates user-facing interaction (chatbot) from data access (mcp_server), mediated by the MCP protocol. The agent (OpenAI LLM) orchestrates tool calls autonomously without ever generating raw SQL.

---

## 2. `mcp_server`

### 2.1 Purpose

Exposes a constrained, policy-validated interface to query the SRF/SRG Jahresbericht dataset (2018–2021). AI agents can call its tools, but they cannot execute arbitrary SQL — every query is expressed as a declarative "query template" and validated against a policy before execution.

### 2.2 Technology Stack

```
Python ≥3.14
├── mcp ≥1.0.0           — MCP server framework (FastMCP)
├── pydantic ≥2.11.7     — Model validation and JSON schema generation
├── duckdb ≥1.4.1        — In-process SQL engine for Parquet queries
├── duckdb-engine ≥0.17.0 — SQLAlchemy dialect for DuckDB
├── sqlalchemy ≥2.0.43   — SQL query builder (prevents SQL injection)
├── pyyaml ≥6.0.2        — Loads policy and catalog configuration
└── structlog ≥24.1.0    — Structured JSON logging
```

### 2.3 Configuration

All configuration is via environment variables:

| Variable                | Default                          | Purpose                                      |
| ----------------------- | -------------------------------- | -------------------------------------------- |
| `MCP_SERVER_HOST`       | `0.0.0.0`                        | Bind address                                 |
| `MCP_SERVER_PORT`       | `8080`                           | Bind port                                    |
| `MCP_SERVER_TRANSPORT`  | `streamable-http`                | Transport: `stdio`, `sse`, `streamable-http` |
| `MCP_SERVER_LOG_LEVEL`  | `INFO`                           | Logging verbosity                            |
| `MCP_DEBUG_ENRICHMENT`  | `false`                          | Enable debug fields in responses             |
| `MCP_DATA_PARQUET_PATH` | `data/Jahresbericht_all.parquet` | Path to Parquet data file                    |

The `AppConfig` dataclass also carries a `contracts_dir: Path` field (resolved automatically from the package root; not configurable via env var) pointing to `src/mcp_server/contracts/`.

### 2.4 MCP Tools Exposed

The server registers exactly **two tools**:

#### `get_catalog`

A glossary lookup tool for discovering column names and their meanings.

- **No argument**: Returns the full catalog of all 9 columns
- **Exact match**: Returns the column definition for a known column name
- **Alias match**: Resolves German synonyms (e.g., `"Kanal"` → `"Sender"`)
- **Fuzzy match**: Uses `difflib.get_close_matches` (cutoff=0.3, top 3) when no exact match exists
- **No match**: Returns error with candidates for selection

This tool enforces a controlled vocabulary — the agent is expected to call it when user phrasing is ambiguous before constructing a query.

Response shape (success):

```json
{
  "ok": true,
  "catalog_version": "v1",
  "selection_required": false,
  "column": "Sender",
  "definition": {
    "description_de": "Sendername (SRF 1, SRF zwei, ...)",
    "type": "string",
    "allowed_examples": ["SRF 1", "SRF zwei"],
    "aliases_de": ["Kanal"]
  }
}
```

Response shape (ambiguous, requires agent to prompt user):

```json
{
  "ok": false,
  "selection_required": true,
  "error": {
    "error_code": "GLOSSARY_TERM_AMBIGUOUS",
    "message": "Unknown glossary term. Select one of the candidates.",
    "details": { "term": "...", "candidates": ["col1", "col2", "col3"] }
  }
}
```

#### `query_data`

The main analytics query tool. Accepts a structured "query template" (not SQL), validates it, builds a SQL query via SQLAlchemy, and executes it on DuckDB against the Parquet file.

Template structure:

```json
{
  "metrics": [{ "column": "Wert", "aggregate": "sum", "alias": "wert_sum" }],
  "filters": [{ "column": "Region", "op": "eq", "value": "DS" }],
  "group_by": ["Sender"],
  "sort": [{ "column": "wert_sum", "direction": "desc" }],
  "limit": 50
}
```

Supported operators: `eq`, `in`, `gte`, `lte`
Supported aggregates: `sum`, `avg`, `min`, `max`, `count`

### 2.5 Service Layer Architecture

The server has a clean 4-stage pipeline for each `query_data` call:

```
Template (dict)
    │
    ▼ Validator
    │  • Pydantic schema check
    │  • Policy check (metrics, filters, group_by, sort, limit)
    ▼
QueryTemplateModel (validated)
    │
    ▼ Planner
    │  • Builds SQLAlchemy Select statement
    │  • Constructs virtual table from policy column set
    ▼
QueryPlan (SQLAlchemy Select)
    │
    ▼ Executor
    │  • Opens in-memory DuckDB connection
    │  • Creates view: jahresbericht_normalized → Parquet file
    │  • Executes statement
    ▼
Rows (list[dict])
    │
    ▼ ResponseBuilder
       • Adds metadata, row_count
       • In debug mode: echoes template, includes sample rows
    ▼
Response (dict) → returned over MCP
```

### 2.6 Policy System

The policy (`contracts/policy.yaml`) is the core security mechanism. It declaratively defines:

- **`filterable`**: Which operators are allowed per column (e.g., `Jahr` allows `gte`/`lte` for ranges; string columns only allow `eq`/`in`)
- **`groupable`**: Which columns can appear in `group_by` (all descriptor columns; `Wert` excluded)
- **`sortable`**: Which columns allow sorting (`Jahr`, `timeslot_start`, `timeslot_end`, `timeslot_duration_minutes`, `Wert`)
- **`aggregates`**: Which aggregate functions are allowed per column (only `Wert` can be aggregated)
- **`limits`**: `default_limit: 20`, `max_limit: 200`

Any violation results in a structured `POLICY_VIOLATION` error returned to the agent, not a server exception.

Additionally, the validator enforces a **cross-region guard**: every query must include exactly one `Region` filter with operator `eq`. This prevents cross-region aggregation, which is statisticaly invalid because each region has a different sender set and audience base.

### 2.7 Data Catalog

The catalog (`contracts/catalog.yaml`) describes the **8 dataset columns** in German:

| Column                      | Type    | Meaning                                                                                        |
| --------------------------- | ------- | ---------------------------------------------------------------------------------------------- |
| `Jahr`                      | integer | Calendar year (2018, 2019, 2020, 2021)                                                         |
| `Region`                    | string  | Language region code: `DS` (Deutsche Schweiz), `SR` (Suisse Romande), `SI` (Svizzera Italiana) |
| `timeslot_start`            | string  | Slot start time (HH:MM:SS, broadcast day 02:00–26:00)                                          |
| `timeslot_end`              | string  | Slot end time (HH:MM:SS, broadcast day 02:00–26:00)                                            |
| `timeslot_duration_minutes` | integer | Slot duration: `15` (quarter-hour), `300` (primetime 18–23h), `1440` (full day)                |
| `Metrik`                    | string  | Metric type: `Rt-T`, `Rt-%`, `NRw-T`, `NRw-%`, `MA-%`, `SD Ø`, `VD Ø`                          |
| `Sender`                    | string  | TV channel name (e.g., `SRF 1`, `SRF zwei`, `RTS Un`, `RSI LA 1`, `ARD`, `ZDF`)                |
| `Wert`                      | number  | Numeric measurement value                                                                      |

Note: the raw Excel files also contain a `Zielgruppen` (audience) column and an `Aktivitäten` column, but both are constant across all rows (`Personen 3+` and `Overnight+7` respectively) and are dropped during transformation — they do not appear in the Parquet file or catalog.

The broadcast day uses an extended time notation: it runs from `02:00:00` to `26:00:00` to keep times monotonically increasing across the midnight boundary. Python's `datetime.time` cannot represent hours ≥ 24, so start/end times are stored as plain strings.

Each column entry includes German aliases, allowed values (exact enum list when finite), example values, and a description.

The catalog also includes two optional lookup sections:

- **`metrics`**: Maps `Metrik` code values (e.g., `Rt-T`, `MA-%`) to human-readable German descriptions and units
- **`timeslot_durations`**: Maps `timeslot_duration_minutes` values (15, 300, 1440) to descriptions

### 2.8 Data Layer

- **Source**: 24 Excel files in `data/raw/` — downloaded from the GitHub Release `data-v1` archive (`jahresberichte-raw-data.zip`)
- **Filename pattern**: `Jahresbericht{YY}_{SRF|nonSRF}-{DS|SI|SR}_{date}_FB.xlsx` — covers years 2018–2021 for all three language regions in both SRF and non-SRF variants
- **Transformed**: `data/Jahresbericht_all.parquet` — all 24 files concatenated into long format (one row per sender per time slot per year/region)
- **Download script**: `src/tools/download_data.py` — fetches the zip archive from GitHub Releases and extracts it into `data/raw/`
- **Transformation script**: `src/tools/load_jahresbericht.py` — loads and transforms each Excel file, then concatenates them

Raw Excel layout per file (102 rows × 65 or 100 columns):

- Row 0: title string (dropped)
- Row 1: L1 header (`Overnight+7`) — forward-filled across columns (constant, dropped after parsing)
- Row 2: metric names (Rt-T, Rt-%, NRw-T, NRw-%, MA-%, SD Ø, VD Ø) — forward-filled
- Row 3: station (Sender) names — SRF files have 9 stations per metric group; nonSRF files have 14
- Rows 4–99: 96 × 15-minute timeslot data rows (02:00–26:00)
- Row 100: "Whole day" summary (02:00–26:00, 1440 minutes)
- Row 101: "18-23h" summary (18:00–23:00, 300 minutes)

The transformation:

1. Parses year and region from the filename (e.g., `Jahresbericht21_SRF-DS_...` → `Jahr=2021`, `Region=DS`)
2. Drops the title row and the constant `Zielgruppen` column (always `Personen 3+`)
3. Forward-fills sparse metric/station headers
4. Parses timeslot strings (e.g., `"07:00:00 - 07:15:00"`) into `timeslot_start`, `timeslot_end`, and `timeslot_duration_minutes`; maps `"Whole day"` and `"18-23h"` to their canonical values
5. Melts the wide matrix into long format: each (timeslot × metric × sender) cell → one row with columns `Jahr, Region, timeslot_start, timeslot_end, timeslot_duration_minutes, Metrik, Sender, Wert`
6. Concatenates all 24 files; outputs a single `Jahresbericht_all.parquet`

The server never reads the Excel files directly; it always reads `Jahresbericht_all.parquet` through a DuckDB in-memory view (`jahresbericht`) created fresh per query.

### 2.9 Logging

Structured JSON logging via `structlog`. The module (`logging.py`) provides:

- `configure_logging(log_level)` — sets up structlog with JSON renderer, ISO timestamps, stdlib backend
- `get_logger(name)` — returns a `FilteringBoundLogger` instance
- `bind_request_context(logger, request_id, ...)` — binds request-scoped fields to a logger for trace correlation

Each tool handler creates a new request ID (`uuid4`), binds it on entry, and logs lifecycle events:

| Event               | Meaning                            |
| ------------------- | ---------------------------------- |
| `request_received`  | Tool call received                 |
| `validation_failed` | Schema or policy validation failed |
| `validated`         | Template passed validation         |
| `planned`           | SQL plan built                     |
| `executed`          | SQL execution completed            |
| `response_sent`     | Response returned to client        |

Each event includes ISO timestamp, log level, logger name, `request_id`, and any additional bound fields.

### 2.10 Tests

| Test file                    | What it tests                                                          |
| ---------------------------- | ---------------------------------------------------------------------- |
| `test_validator.py`          | Valid queries pass; invalid operator rejected; limit exceeded rejected |
| `test_planner.py`            | Full pipeline: validate → plan → execute against real Parquet data     |
| `test_response_builder.py`   | Default vs debug mode response shape                                   |
| `test_policy_enforcement.py` | Non-aggregatable columns rejected in metrics                           |
| `test_mcp_server.py`         | Module-level existence/import tests                                    |

---

## 3. `chatbot`

### 3.1 Purpose

A web-based chatbot that connects to the MCP server, fetches its tool definitions, and orchestrates an OpenAI LLM as an agent to answer natural-language queries about the Jahresbericht data. The UI is a [Gradio](https://gradio.app) `ChatInterface` served over HTTP.

### 3.2 Technology Stack

```
Python ≥3.14
├── openai ≥2.0.0   — Chat completion API with tool calling
├── mcp ≥1.0.0      — MCP client (fetches tool specs from server)
└── gradio ≥5.0.0   — Web chat UI (ChatInterface)
```

### 3.3 Configuration

| Variable         | Default                     | Purpose                    |
| ---------------- | --------------------------- | -------------------------- |
| `OPENAI_API_KEY` | (required)                  | OpenAI authentication      |
| `OPENAI_MODEL`   | `gpt-4o-mini`               | Model for chat completions |
| `MCP_SERVER_URL` | `http://localhost:8080/mcp` | MCP server endpoint        |
| `GRADIO_PORT`    | `7860`                      | Port for Gradio web UI     |

### 3.4 System Prompt

The system prompt is written in German and includes:

- A strict no-SQL rule (tool-only operation)
- A catalog-first workflow: call `get_catalog` for unknown terms; if `selection_required=true`, ask the user to clarify
- A no-interpretation rule: report facts only, no trends or predictions
- A region requirement: every query must include exactly one region (DS, SR, or SI); ask the user if missing
- A data-scope description: Mediapulse panel data 2018–2021, "Personen 3+" only, structured TV metrics per sender/region/time slot
- A list of unavailable data (demographics, individual shows, streaming, etc.) with a standard fallback phrase

This constrains the LLM to tool-only operation and enforces a specific workflow: catalog lookup → query, while setting accurate user expectations about data availability.

### 3.5 Agent Loop

The chatbot implements a Gradio-driven agentic loop:

```
Startup:
  1. Load OpenAI client
  2. Build Gradio ChatInterface with respond() callback
  3. Launch Gradio server (HTTP on GRADIO_PORT)

Per user message (respond(message, history)):
  1. Open a fresh MCP session to MCP_SERVER_URL
  2. Fetch available tools → convert to OpenAI function-calling format
  3. Build OpenAI messages: system prompt + history + new user message
  4. Inner loop (up to _MAX_TOOL_ROUNDS=15 iterations):
       - POST to OpenAI: messages + tool specs
       - If no tool_calls: return final text to Gradio
       - For each tool_call:
           - Parse arguments
           - Call MCP tool via session
           - Append tool result to messages
       - Continue inner loop (feed results back to LLM)
  5. If max rounds reached: return error message
```

The inner loop is key: the LLM can chain multiple tool calls (e.g., first `get_catalog`, then `query_data`) before producing a final text response. Conversation history across turns is managed by Gradio and passed as `history` to each `respond()` call. A new MCP session is opened per turn.

### 3.6 Tool Conversion

MCP tools are converted to OpenAI function-calling format:

```python
{
  "type": "function",
  "function": {
    "name": tool.name,
    "description": tool.description,
    "parameters": tool.inputSchema  # JSON Schema
  }
}
```

The LLM uses these to decide which tool to call and with what arguments.

### 3.7 Notable Implementation Details

- **Temperature = 1**: Maximum randomness — the LLM has freedom in how it chooses and chains tool calls
- **No streaming**: Waits for full completions before processing tool calls
- **Conversation state**: Managed by Gradio; passed as `history: list[dict[str, str]]` per turn. Not persisted across server restarts.
- **MCP session per turn**: A fresh `streamable_http_client` session is opened for each `respond()` call; stateless design matches Gradio's callback model
- **Max tool rounds**: `_MAX_TOOL_ROUNDS = 15` prevents infinite loops in the inner tool-calling loop
- **Error surface**: If OpenAI or MCP connections fail, the error is returned as a Gradio chat reply rather than crashing the server
- **`_to_jsonable()`**: Recursively converts Pydantic model instances to plain dicts for JSON serialization before passing tool results back to OpenAI

### 3.8 Tests

Minimal — only the `greet()` utility function is tested (default greeting, custom name, parametrized). The main agent loop has no automated tests.

---

## 4. System Architecture

### 4.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    User (Web Browser)                        │
└──────────────────────────────┬───────────────────────────────┘
                               │ natural language
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                Chatbot (Gradio Web App + MCP Client)         │
│                                                              │
│  ┌─────────────┐    ┌────────────────┐    ┌──────────────┐  │
│  │ Gradio Chat │    │  OpenAI Agent  │    │  MCP Client  │  │
│  │  Interface  │◄──►│  (gpt-4o-mini) │◄──►│ (per-turn)   │  │
│  └─────────────┘    └────────────────┘    └──────┬───────┘  │
└──────────────────────────────────────────────────┼──────────┘
                                                   │ HTTP / streamable-http
                                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                    MCP Server                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Tool: get_catalog                                  │    │
│  │  • Fuzzy column lookup                              │    │
│  │  • Alias resolution                                 │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Tool: query_data                                   │    │
│  │  Validator → Planner → Executor → ResponseBuilder   │    │
│  └───────────────────────────────┬─────────────────────┘    │
│                                  │                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Contracts (YAML / JSON Schema)                     │    │
│  │  • policy.yaml  • catalog.yaml  • schema.json       │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬───────────────────────────┘
                                   │ DuckDB in-memory SQL
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│              Parquet Data (jahresbericht_normalized)          │
│              47 KB — SRF/SRG Jahresbericht 2021              │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Data Flow for a Typical Query

1. User types: _"What was the average viewership for SRF 1 in prime time?"_
2. OpenAI decides to call `get_catalog(term="viewership")` → MCP server returns column definition for `Wert`
3. OpenAI decides to call `get_catalog(term="prime time")` → MCP server returns fuzzy candidates including `timeslot_duration_minutes` and `timeslot_start`
4. OpenAI calls `query_data` with a structured template (metrics: avg Wert, filters: Region eq "DS", Sender eq "SRF 1", group_by: timeslot_start)
5. MCP server validates template against policy → builds SQL → executes on DuckDB → returns rows
6. OpenAI formats a natural-language answer referencing the filters and dimensions used
7. User sees the final text response

---

## 5. Design Decisions and Rationale

### 5.1 No Raw SQL Exposure

The most fundamental design choice: the LLM never sees or generates SQL. It only works with a declarative `QueryTemplateModel`. This:

- Prevents SQL injection entirely at the architecture level
- Keeps the LLM's action space small and auditable
- Allows the server to enforce access policies on every query

### 5.2 Policy-as-Code

The policy YAML is the single source of truth for what queries are legal. Changing access rights requires only editing `policy.yaml`, not application code. This separation makes the system auditable and extensible.

### 5.3 Catalog-First Design

The `get_catalog` tool forces structured term resolution before querying. The agent is instructed to consult it for unknown terms, which maps fuzzy user language to precise column names. This reduces hallucination of column names.

### 5.4 DuckDB + Parquet

Using DuckDB with a Parquet file provides:

- Zero infrastructure (no database server)
- Columnar compression (47 KB vs 131 KB CSV)
- Fast analytical queries via vectorized execution
- Each query gets a fresh in-memory DuckDB connection (stateless)

### 5.5 SQLAlchemy as Query Builder

SQLAlchemy is used only as a SQL builder (not as ORM), with DuckDB as the execution engine. This provides:

- Parameterized queries (no string interpolation — SQL injection safe)
- A clean programmatic API for building SELECT statements
- Type safety via Python objects rather than string manipulation

### 5.6 MCP as the Integration Layer

Using the Model Context Protocol allows:

- Protocol-level separation between LLM client and data server
- Potential for multiple different clients (Claude, GPT, custom) connecting to the same server
- Standard tool discovery and invocation semantics
- Transport flexibility (stdio for local, HTTP for network)

---

## 6. Key Observations and Findings

### Strengths

1. **Security by design**: No SQL exposure, policy-validated queries, parameterized execution — hard to abuse
2. **Agent-friendly contracts**: Structured error codes, fuzzy matching, `selection_required` flags give the LLM clear signals on how to recover from failures
3. **Clean service separation**: Validator / Planner / Executor / ResponseBuilder are independent and individually testable
4. **Structured logging**: JSON events with request IDs enable tracing and debugging
5. **Multilingual support**: German column names, aliases, and descriptions throughout
6. **Debug mode**: The `MCP_DEBUG_ENRICHMENT` flag makes troubleshooting server-side query execution easy without code changes

### Limitations / Gaps

1. **Single dataset**: The system is hard-wired to one Parquet file and one table (`jahresbericht`). Adding a second dataset would require significant extension.
2. **No auth on MCP server**: The HTTP transport has no authentication — any client that can reach the port can query data.
3. **In-memory DuckDB per request**: A new DuckDB connection is created for every `query_data` call. For high concurrency this would be inefficient (though fine for PoC).
4. **Minimal chatbot tests**: The agent loop is entirely untested in automated tests.
5. **Temperature=1 for agent**: Maximum randomness for tool-calling may produce inconsistent behavior in production.
6. **Four-year dataset, update pipeline absent**: Data covers 2018–2021 but the transformation pipeline must be re-run manually to add new years; there is no automated refresh or incremental update mechanism.
7. **No streaming responses**: The chatbot waits for full completions, which means long tool chains feel slow.
8. **MCP session per turn**: Re-establishing the HTTP connection on every Gradio turn adds latency; a pooled session would be more efficient for production use.

### Extensibility Hooks

- **New tools**: Additional MCP tools can be registered in `main.py` with minimal changes
- **New datasets**: Adding a second Parquet file would require new policy + catalog YAML files and a new executor path
- **Different LLMs**: The chatbot is OpenAI-specific, but since MCP is standard, a Claude or Mistral client could connect to the same server
- **Policy updates**: Changing filterable/groupable/aggregatable columns requires only editing `policy.yaml`

---

## 7. File Index

```
poc/apps/
├── mcp_server/
│   ├── pyproject.toml                        — Project config, deps (Python ≥3.14, structlog)
│   ├── data/
│   │   ├── raw/                               — Raw source Excel files (24 .xlsx files, downloaded via download_data.py)
│   │   └── Jahresbericht_all.parquet          — Normalized multi-year query data
│   ├── src/
│   │   ├── mcp_server/
│   │   │   ├── main.py                        — Entry point, FastMCP setup, tool registration
│   │   │   ├── config.py                      — AppConfig dataclass, env var loading (incl. contracts_dir)
│   │   │   ├── logging.py                     — structlog configuration, get_logger, bind_request_context
│   │   │   ├── contracts/
│   │   │   │   ├── models.py                  — QueryTemplateModel, MetricModel, FilterModel, etc.
│   │   │   │   ├── catalog_models.py          — CatalogModel, CatalogColumnModel, MetricDefinitionModel, TimeslotDurationModel
│   │   │   │   ├── policy_models.py           — PolicyModel, LimitsModel
│   │   │   │   ├── catalog.yaml               — Column descriptions, aliases, allowed values, metric/timeslot lookups
│   │   │   │   ├── policy.yaml                — Access policy (filterable, groupable, etc.)
│   │   │   │   └── query_template.schema.json — JSON Schema for QueryTemplateModel
│   │   │   ├── services/
│   │   │   │   ├── validator.py               — Template + policy validation (incl. Region guard)
│   │   │   │   ├── planner.py                 — SQLAlchemy query plan builder
│   │   │   │   ├── executor_duckdb.py         — DuckDB execution engine (view: jahresbericht)
│   │   │   │   ├── response_builder.py        — Response assembly
│   │   │   │   └── loaders.py                 — Policy/catalog YAML loaders, schema export
│   │   │   └── tools/
│   │   │       ├── get_catalog.py             — get_catalog MCP tool handler
│   │   │       └── query_data.py              — query_data MCP tool handler
│   │   └── tools/
│   │       ├── download_data.py           — Downloads raw Excel zip from GitHub Release data-v1 → data/raw/
│   │       └── load_jahresbericht.py      — Loads & transforms all Excel files → Jahresbericht_all.parquet
│   └── tests/
│       ├── test_validator.py                  — Validator unit tests
│       ├── test_planner.py                    — Planner integration test (real Parquet)
│       ├── test_response_builder.py           — Response builder tests
│       ├── test_policy_enforcement.py         — Policy enforcement tests
│       └── test_mcp_server.py                 — Basic module tests
└── chatbot/
    ├── pyproject.toml                         — Project config, deps (openai, mcp, gradio)
    ├── src/
    │   └── chatbot/
    │       └── main.py                        — Gradio ChatInterface, agent loop, OpenAI integration
    └── tests/
        └── test_main.py                       — greet() function tests only
```
