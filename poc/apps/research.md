# Research Report: `poc/apps/` — Deep Dive

> Analysis of the two applications in `poc/apps/`: `mcp_server` and `chatbot`.
> These form a proof-of-concept AI data assistant system for SRF/SRG Jahresbericht analytics.

---

## 1. Overview

The system has two components that work together:

| App | Role | Protocol |
|-----|------|----------|
| `mcp_server` | Policy-controlled data query backend | MCP (Model Context Protocol) server |
| `chatbot` | Interactive CLI agent | MCP client + OpenAI tool-calling |

The architecture separates user-facing interaction (chatbot) from data access (mcp_server), mediated by the MCP protocol. The agent (OpenAI LLM) orchestrates tool calls autonomously without ever generating raw SQL.

---

## 2. `mcp_server`

### 2.1 Purpose

Exposes a constrained, policy-validated interface to query the SRF Jahresbericht 2021 dataset. AI agents can call its tools, but they cannot execute arbitrary SQL — every query is expressed as a declarative "query template" and validated against a policy before execution.

### 2.2 Technology Stack

```
Python ≥3.14
├── mcp ≥1.0.0           — MCP server framework (FastMCP)
├── pydantic ≥2.11.7     — Model validation and JSON schema generation
├── duckdb ≥1.4.1        — In-process SQL engine for Parquet queries
├── duckdb-engine ≥0.17.0 — SQLAlchemy dialect for DuckDB
├── sqlalchemy ≥2.0.43   — SQL query builder (prevents SQL injection)
└── pyyaml ≥6.0.2        — Loads policy and catalog configuration
```

### 2.3 Configuration

All configuration is via environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_SERVER_HOST` | `0.0.0.0` | Bind address |
| `MCP_SERVER_PORT` | `8080` | Bind port |
| `MCP_SERVER_TRANSPORT` | `streamable-http` | Transport: `stdio`, `sse`, `streamable-http` |
| `MCP_SERVER_LOG_LEVEL` | `INFO` | Logging verbosity |
| `MCP_DEBUG_ENRICHMENT` | `false` | Enable debug fields in responses |
| `MCP_DATA_PARQUET_PATH` | bundled default | Path to Parquet data file |

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
  "metrics": [
    { "column": "Wert", "aggregate": "sum", "alias": "wert_sum" }
  ],
  "filters": [
    { "column": "Region", "op": "eq", "value": "Deutsche Schweiz" }
  ],
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
- **`sortable`**: Which columns allow sorting (`Zeitschienen`, `Jahr`, `Wert`)
- **`aggregates`**: Which aggregate functions are allowed per column (only `Wert` can be aggregated)
- **`limits`**: `default_limit: 20`, `max_limit: 200`

Any violation results in a structured `POLICY_VIOLATION` error returned to the agent, not a server exception.

### 2.7 Data Catalog

The catalog (`contracts/catalog.yaml`) describes the 9 dataset columns in German:

| Column | Type | Meaning |
|--------|------|---------|
| `Zeitschienen` | string | 15-minute broadcast time slots (e.g., `"07:00:00 - 07:15:00"`) |
| `Facts` | string | Metric type identifier (e.g., `"Rt-T"`) |
| `Aktivitäten` | string | Activity measurement window (e.g., `"Overnight+7"`) |
| `Zielgruppe` | string | Target audience group (e.g., `"Personen 3+"`) |
| `Region` | string | Swiss language region (e.g., `"Deutsche Schweiz"`) |
| `Jahr` | integer | Calendar year |
| `Zeitintervall` | string | Measurement interval (e.g., `"15 min"`) |
| `Sender` | string | TV channel name (e.g., `"SRF 1"`, `"SRF zwei"`) |
| `Wert` | number | Numeric measurement value |

Each column entry also includes German aliases (e.g., `Sender` → `["Kanal"]`) and example values for agent guidance.

### 2.8 Data Layer

- **Source**: `data/Jahresbericht21_SRF-DS.csv` (131 KB) — raw wide-format CSV with one column per sender
- **Transformed**: `data/Jahresbericht21_SRF-DS.normalized.parquet` (47 KB) — melted to long format (one row per sender per time slot)
- **Transformation script**: `src/tools/transform_jahresbericht.py`

The transformation:
1. Melts sender columns (`SRF 1`, `SRF zwei`, etc.) into a single `Sender` + `Wert` pair per row
2. Drops summary aggregate columns (`SRG SSR Total`, `SRF Total`, `Restliche SRG SSR`)
3. Adds a `Sendergruppen` column (list of group membership per sender)
4. Converts values to float, optionally drops NaN rows
5. Outputs normalized Parquet

The server never reads the CSV directly; it always reads the normalized Parquet through a DuckDB in-memory view created fresh per query.

### 2.9 Logging

Structured JSON logging via `log_event()`. Each request lifecycle emits events:

| Event | Meaning |
|-------|---------|
| `request_received` | Tool call received |
| `validation_failed` | Schema or policy validation failed |
| `validated` | Template passed validation |
| `planned` | SQL plan built |
| `executed` | SQL execution completed |
| `response_sent` | Response returned to client |

Each event includes `timestamp` (ms since epoch), `event`, `request_id`, and optional additional fields.

### 2.10 Tests

| Test file | What it tests |
|-----------|---------------|
| `test_validator.py` | Valid queries pass; invalid operator rejected; limit exceeded rejected |
| `test_planner.py` | Full pipeline: validate → plan → execute against real Parquet data |
| `test_response_builder.py` | Default vs debug mode response shape |
| `test_policy_enforcement.py` | Non-aggregatable columns rejected in metrics |
| `test_mcp_server.py` | Module-level existence/import tests |

---

## 3. `chatbot`

### 3.1 Purpose

An interactive command-line chatbot that connects to the MCP server, fetches its tool definitions, and orchestrates an OpenAI LLM as an agent to answer natural-language queries about the Jahresbericht data.

### 3.2 Technology Stack

```
Python ≥3.14
├── openai ≥2.0.0   — Chat completion API with tool calling
└── mcp ≥1.0.0      — MCP client (fetches tool specs from server)
```

### 3.3 Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | (required) | OpenAI authentication |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model for chat completions |
| `MCP_SERVER_URL` | `http://localhost:8080/mcp` | MCP server endpoint |

### 3.4 System Prompt

```
You are a data assistant for Jahresbericht analytics.
Never generate SQL. Only use the provided tools.
Use get_catalog first when user terms are unclear.
If a glossary term is ambiguous and selection_required is true, ask the user to choose.
In final answers, mention the filters and dimensions you used.
```

This constrains the LLM to tool-only operation and enforces a specific workflow: catalog lookup → query.

### 3.5 Agent Loop

The chatbot implements a standard agentic loop:

```
1. Connect to MCP server → fetch available tools
2. Convert MCP tool specs → OpenAI function-calling format
3. Print welcome message

Loop:
  a. Read user input (or exit on "exit"/"quit")
  b. Add user message to conversation history
  c. Inner loop:
       - POST to OpenAI: system prompt + history + tools
       - If response has no tool_calls: print text, break inner loop
       - For each tool_call:
           - Print "calling tool: <name>" to user
           - Call corresponding MCP tool with arguments
           - Append tool result to conversation history
       - Continue inner loop (feed results back to LLM)
```

The inner loop is key: the LLM can chain multiple tool calls (e.g., first `get_catalog`, then `query_data`) before producing a final text response.

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
- **Conversation state**: Full message history accumulated in memory per session (not persisted)
- **Error surface**: If OpenAI or MCP connections fail, friendly error messages are printed rather than raw exceptions
- **`_to_jsonable()`**: Recursively converts Pydantic model instances to plain dicts for JSON serialization before passing tool results back to OpenAI

### 3.8 Tests

Minimal — only the `greet()` utility function is tested (default greeting, custom name, parametrized). The main agent loop has no automated tests.

---

## 4. System Architecture

### 4.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                        User (CLI)                            │
└──────────────────────────────┬───────────────────────────────┘
                               │ natural language
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Chatbot (MCP Client)                      │
│                                                              │
│  ┌─────────────┐    ┌────────────────┐    ┌──────────────┐  │
│  │ Conversation│    │  OpenAI Agent  │    │  MCP Client  │  │
│  │  History    │◄──►│  (gpt-4o-mini) │◄──►│  (tool proxy)│  │
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
3. OpenAI decides to call `get_catalog(term="prime time")` → MCP server returns fuzzy candidates including `Zeitschienen`
4. OpenAI calls `query_data` with a structured template (metrics: avg Wert, filters: Sender eq "SRF 1", group_by: Zeitschienen)
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

1. **Single dataset**: The system is hard-wired to one Parquet file and one table (`jahresbericht_normalized`). Adding a second dataset would require significant extension.
2. **No auth on MCP server**: The HTTP transport has no authentication — any client that can reach the port can query data.
3. **In-memory DuckDB per request**: A new DuckDB connection is created for every `query_data` call. For high concurrency this would be inefficient (though fine for PoC).
4. **Minimal chatbot tests**: The agent loop is entirely untested in automated tests.
5. **Temperature=1 for agent**: Maximum randomness for tool-calling may produce inconsistent behavior in production.
6. **Single year of data**: Only 2021 data is bundled — multi-year analysis or update pipelines are not addressed.
7. **No streaming responses**: The chatbot waits for full completions, which means long tool chains feel slow.

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
│   ├── pyproject.toml                        — Project config, deps (Python ≥3.14)
│   ├── data/
│   │   ├── Jahresbericht21_SRF-DS.csv         — Raw source data (131 KB)
│   │   └── Jahresbericht21_SRF-DS.normalized.parquet — Normalized query data (47 KB)
│   ├── src/
│   │   ├── mcp_server/
│   │   │   ├── main.py                        — Entry point, FastMCP setup, tool registration
│   │   │   ├── config.py                      — AppConfig dataclass, env var loading
│   │   │   ├── logging.py                     — Structured JSON event logger
│   │   │   ├── contracts/
│   │   │   │   ├── models.py                  — QueryTemplateModel, MetricModel, FilterModel, etc.
│   │   │   │   ├── catalog_models.py          — CatalogModel, CatalogColumnModel
│   │   │   │   ├── policy_models.py           — PolicyModel, LimitsModel
│   │   │   │   ├── catalog.yaml               — Column descriptions, aliases, examples
│   │   │   │   ├── policy.yaml                — Access policy (filterable, groupable, etc.)
│   │   │   │   └── query_template.schema.json — JSON Schema for QueryTemplateModel
│   │   │   ├── services/
│   │   │   │   ├── validator.py               — Template + policy validation
│   │   │   │   ├── planner.py                 — SQLAlchemy query plan builder
│   │   │   │   ├── executor_duckdb.py         — DuckDB execution engine
│   │   │   │   ├── response_builder.py        — Response assembly
│   │   │   │   └── loaders.py                 — Policy/catalog YAML loaders, schema export
│   │   │   └── tools/
│   │   │       ├── get_catalog.py             — get_catalog MCP tool handler
│   │   │       └── query_data.py              — query_data MCP tool handler
│   │   └── tools/
│   │       └── transform_jahresbericht.py     — CSV → Parquet normalization script
│   └── tests/
│       ├── test_validator.py                  — Validator unit tests
│       ├── test_planner.py                    — Planner integration test (real Parquet)
│       ├── test_response_builder.py           — Response builder tests
│       ├── test_policy_enforcement.py         — Policy enforcement tests
│       └── test_mcp_server.py                 — Basic module tests
└── chatbot/
    ├── pyproject.toml                         — Project config, deps (openai, mcp)
    ├── src/
    │   └── chatbot/
    │       └── main.py                        — Agent loop, OpenAI integration, CLI
    └── tests/
        └── test_main.py                       — greet() function tests only
```
