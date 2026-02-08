# AGENTS.md

This file provides guidance for AI agents working with this codebase.

## Project Overview

This is a **uv Workspace** based Python project implementing a chatbot backed by MCP (Model Context Protocol) servers.

## Directory Structure

```
poc/
├── apps/                       # Application packages (workspace members)
│   ├── chatbot/                # Chatbot application
│   │   ├── pyproject.toml      # App-specific config and dependencies
│   │   ├── src/chatbot/        # Source code
│   │   └── tests/              # App-specific tests
│   └── mcp_server/             # MCP Server application
│       ├── pyproject.toml      # App-specific config and dependencies
│       ├── src/mcp_server/     # Source code
│       └── tests/              # App-specific tests
├── docker/                     # Dockerfiles per service
│   ├── chatbot/Dockerfile
│   └── mcp_server/Dockerfile
├── pyproject.toml              # Workspace root config (shared dev tools)
├── uv.lock                     # Lock file (do not edit manually)
└── docker-compose.yml          # Container orchestration
```

## Development Commands

All commands should be run from the `poc/` directory.

### Setup
```bash
uv sync --all-extras           # Install all dependencies
uv run pre-commit install      # Set up git hooks
```

### Running Applications
```bash
uv run --package chatbot python -m chatbot.main
uv run --package mcp-server python -m mcp_server.main
```

### Quality Checks
```bash
uv run pytest                  # Run all tests
uv run ty check                # Type checking
uv run ruff check .            # Linting
uv run ruff format .           # Formatting
uv run pre-commit run --all-files  # All pre-commit hooks
```

### Docker
```bash
docker compose build           # Build images
docker compose up              # Run containers
docker compose down            # Stop containers
```

## Key Configuration Files

| File | Purpose |
|------|---------|
| `pyproject.toml` (root) | Workspace config, shared dev dependencies, tool settings |
| `apps/*/pyproject.toml` | Per-app dependencies and build config |
| `.pre-commit-config.yaml` | Pre-commit hooks (ruff, ty) |
| `docker-compose.yml` | Container orchestration |

## Adding Dependencies

```bash
# Add to a specific app
uv add --package chatbot <dependency>
uv add --package mcp-server <dependency>

# Add dev dependency to workspace root
uv add --dev <dependency>

# Always update lock file after changes
uv lock
```

## Code Style

- **Formatter/Linter:** Ruff (configured in root `pyproject.toml`)
- **Type Checker:** ty
- **Line Length:** 100 characters
- **Python Version:** 3.14+

## Testing Guidelines

- Tests live in `apps/<app>/tests/`
- Do NOT add `__init__.py` to test directories (causes pytest collection issues)
- Use pytest with asyncio support enabled

## Docker Guidelines

- Each app has its own Dockerfile in `docker/<app>/Dockerfile`
- Dockerfiles only copy the specific app directory they need
- Use `--package <name>` flag when running apps in containers

## CI/CD

GitHub Actions workflow located at `/.github/workflows/poc-ci.yml`:
- Runs on changes to `poc/**`
- Executes pre-commit hooks (lint, format, type check)
- Runs pytest
