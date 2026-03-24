# Proof of Concept

A chatbot backed by an OpenAI agent that queries Swiss TV audience statistics (Mediapulse Jahresbericht 2018–2021) through constrained MCP (Model Context Protocol) servers. The chatbot exposes a Gradio web UI and enforces domain constraints via system prompts and server-side policy validation.

## Project Overview

The PoC demonstrates:
- A Python-based chatbot using the OpenAI API (tool-calling agent loop)
- Two MCP server implementations for constrained, read-only data access
- Docker Compose setup for easy deployment (3 services)
- Code quality enforcement with pre-commit hooks and CI/CD

## Prerequisites

- **uv** (installed via pipx): `pipx install uv`
- **Python 3.14+** (installed via uv, if not already available): `uv python install 3.14`
  > Do not use Python 3.14 as your system default if it is not already — it can break system tooling.
- **Docker** and **Docker Compose**
- **Git**

## Project Structure

```
poc/
├── apps/                            # uv workspace members
│   ├── chatbot/
│   │   ├── pyproject.toml
│   │   ├── src/chatbot/
│   │   │   ├── main.py              # Gradio UI + OpenAI agent loop
│   │   │   └── system_prompt_v2.py  # Current system prompt (German)
│   │   └── tests/
│   └── mcp_server/
│       ├── pyproject.toml
│       ├── src/
│       │   ├── mcp_server/          # v1: schema-validated, DuckDB-backed
│       │   │   ├── main.py
│       │   │   ├── contracts/       # policy.yaml, catalog.yaml, JSON schema
│       │   │   └── services/        # validator, planner, executor, response builder
│       │   ├── mcp_server_v2/       # v2: pandas-based, pivot support
│       │   │   └── main.py
│       │   └── tools/               # data pipeline scripts
│       │       ├── download_data.py
│       │       ├── load_jahresbericht.py    # → Jahresbericht_all.parquet (v1)
│       │       └── load_jahresbericht_v2.py # → Jahresbericht_v2.parquet (v2)
│       └── tests/
├── docker/
│   ├── chatbot/Dockerfile           # Gradio chatbot image
│   ├── mcp_server/Dockerfile        # v1 MCP server (multi-stage: data → prod)
│   └── mcp_server_v2/Dockerfile     # v2 MCP server (multi-stage: data → prod)
├── redteam/                         # promptfoo red-team evaluation configs & results
├── pyproject.toml                   # Workspace root config (shared dev tools)
├── uv.lock                          # Dependency lock file
├── docker-compose.yml               # 3-service orchestration
└── .env.example                     # Environment variables template

# Note: GitHub Actions workflow is at repo root: /.github/workflows/poc-ci.yml
```

## Setup Instructions

### 1. Initialize the Project

```bash
# Navigate to the poc directory
cd poc

# Install all dependencies (creates .venv)
uv sync --all-extras
```

### 2. Set Up Pre-commit Hooks

```bash
uv run pre-commit install

# (Optional) Run hooks on all files to verify setup
uv run pre-commit run --all-files
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 4. Verify the Setup

```bash
uv run pytest -v
uv run ty check
```

## Data Setup (Raw Jahresbericht Excel Files)

The 24 raw `.xlsx` source files are distributed as a single archive attached to the
[`data-v1` GitHub Release](https://github.com/CeVauDe/cas-msed-transferarbeit/releases/tag/data-v1).
Run the download script once before any transformation or Parquet generation step:

```bash
# Download and extract into apps/mcp_server/data/raw/
uv run --package mcp-server python apps/mcp_server/src/tools/download_data.py
```

This places 24 `Jahresbericht*.xlsx` files into `apps/mcp_server/data/raw/`.
The directory is git-ignored; re-run the script on any fresh checkout.

## Data Transformation

### MCP Server v1 (DuckDB)

```bash
uv run --package mcp-server python apps/mcp_server/src/tools/load_jahresbericht.py
# Output: apps/mcp_server/data/Jahresbericht_all.parquet
```

Normalizes the source Excel files into a long-format Parquet dataset (one row per timeslot/metric/sender combination).

Main columns:
- `Zeitschienen` (string): source timeslot label
- `Facts` (string): tracked metric (e.g. `MA-%`, `VD Ø [Sekunden]`)
- `Aktivitäten`, `Zielgruppe` (string)
- `Region` (string): `Deutsche Schweiz`, `Suisse romande`, `Svizzera italiana`
- `Jahr` (int): 2018–2021
- `Zeitintervall` (string)
- `Sender` (string): individual broadcaster
- `Wert` (float): numeric value
- `Sendergruppen` (list[string]): group memberships for rollups

### MCP Server v2 (pandas)

```bash
uv run --package mcp-server python apps/mcp_server/src/tools/load_jahresbericht_v2.py
# Output: apps/mcp_server/data/Jahresbericht_v2.parquet
```

Alternative schema optimized for the pandas-based v2 server (pivot table support).

## MCP Servers

### v1 — Schema-validated, DuckDB-backed (port 8080)

Exposes read-only tools with strict policy enforcement. All queries go through schema validation, policy checks, SQL plan generation, and DuckDB execution.

**Tools:**
- `query_data(template)` — executes a validated query on the Parquet dataset
- `get_catalog(term=None)` — returns column metadata and allowed values

**Query template format:**

```json
{
  "metrics": [{"column": "Wert", "aggregate": "sum", "alias": "wert_sum"}],
  "filters": [{"column": "Region", "op": "eq", "value": "Deutsche Schweiz"}],
  "group_by": ["Zeitschienen"],
  "sort": [{"column": "wert_sum", "direction": "desc"}]
}
```

Allowed aggregates: `sum`, `avg`, `min`, `max`, `count`
Allowed operators: `eq`, `in`, `gte`, `lte`

**Error codes:**
- `SCHEMA_VALIDATION_ERROR` — input schema invalid
- `POLICY_VIOLATION` — column/operator/aggregate/group/sort/limit not allowed
- `GLOSSARY_TERM_AMBIGUOUS` — unknown glossary term, candidate selection required
- `EXECUTION_ERROR` — validated query failed during execution

**Run locally:**

```bash
uv run --package mcp-server python -m mcp_server.main
```

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_HOST` | `0.0.0.0` | Bind address |
| `MCP_SERVER_PORT` | `8080` | Port |
| `MCP_SERVER_TRANSPORT` | `streamable-http` | `stdio\|sse\|streamable-http` |
| `MCP_SERVER_LOG_LEVEL` | `INFO` | Log verbosity |
| `MCP_DEBUG_ENRICHMENT` | `false` | Include debug fields in responses |
| `MCP_DATA_PARQUET_PATH` | `apps/mcp_server/data/Jahresbericht_all.parquet` | Dataset path |

### v2 — Pandas-based, pivot support (port 8081)

Simplified implementation using pandas DataFrame operations. Supports pivot tables. Tool name: `abfrage_jahresbericht`.

**Run locally:**

```bash
uv run --package mcp-server python -m mcp_server_v2.main
```

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_SERVER_V2_HOST` | `0.0.0.0` | Bind address |
| `MCP_SERVER_V2_PORT` | `8081` | Port |
| `MCP_SERVER_V2_TRANSPORT` | `streamable-http` | Transport protocol |
| `MCP_DATA_V2_PARQUET_PATH` | `apps/mcp_server/data/Jahresbericht_v2.parquet` | Dataset path |

## Chatbot

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model used by the agent |
| `MCP_SERVER_URL` | `http://localhost:8081/mcp` | MCP server endpoint |
| `GRADIO_PORT` | `7860` | Gradio web UI port |

**Run locally:**

```bash
uv run --package chatbot python -m chatbot.main
# Open http://localhost:7860
```

## Docker Setup

### Quick Start (fresh clone)

The only prerequisites are Docker, Docker Compose, and an OpenAI API key:

```bash
cd poc
cp .env.example .env           # add OPENAI_API_KEY
docker compose up --build      # builds images, downloads data, starts all services
# Open http://localhost:7860
```

The MCP server Dockerfiles use **multi-stage builds**: stage 1 downloads the raw Excel files from GitHub Releases and transforms them into Parquet. Stage 2 is the lean production image. No local Python, uv, or manual data setup is required.

### Services

| Service | Port | Description |
|---------|------|-------------|
| `chatbot` | 7860 | Gradio web UI + OpenAI agent |
| `mcp-server` | 8080 | MCP server v1 (DuckDB, schema-validated) |
| `mcp-server-v2` | 8081 | MCP server v2 (pandas, pivot support) |

The chatbot connects to `mcp-server-v2` by default and starts only after it reports healthy.

### Commands

```bash
docker compose build           # build images (downloads & generates data)
docker compose up              # start all services
docker compose up -d           # start in detached mode
docker compose logs -f         # view logs
docker compose down            # stop all services
```

## Development Workflow

### Running Code Quality Checks

Pre-commit hooks run automatically on `git commit`. To run them manually:

```bash
uv run pre-commit run              # staged files only
uv run pre-commit run --all-files  # all files
uv run pre-commit run ruff --all-files
```

### Running Tests

```bash
uv run pytest          # all tests
uv run pytest -v       # verbose
```

### Type Checking

```bash
uv run ty check
```

### Linting and Formatting

```bash
uv run ruff check .         # lint
uv run ruff check --fix .   # lint + auto-fix
uv run ruff format .        # format
uv run ruff format --check .
```

## CI/CD Pipeline

GitHub Actions workflow at `/.github/workflows/poc-ci.yml` runs on every push/PR to `main` affecting `poc/**`:

1. **lint-and-type-check** — pre-commit hooks (ruff, ty, YAML/TOML validation)
2. **test** — downloads data, transforms to Parquet, runs pytest

## Adding Dependencies

```bash
uv add --package chatbot <package>     # chatbot app dependency
uv add --package mcp-server <package>  # MCP server dependency
uv add --dev <package>                 # shared dev dependency (workspace root)
uv lock                                # update lock file
```

## Common Issues

### Pre-commit Hook Failures

Hooks often auto-fix issues. Re-stage and commit again:

```bash
git add -u
git commit -m "Your message"
```

### Docker Build Failures

The `uv.lock` file must be up to date:

```bash
uv lock
docker compose build
```

### Troubleshooting MCP Server

- Missing Parquet file: run the data transformation scripts (see Data Transformation above) or let Docker build handle it.
- Empty query results: validate filter values against `get_catalog` output.
- Debug fields missing: set `MCP_DEBUG_ENRICHMENT=true`.
