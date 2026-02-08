# AGENTS.md

This file provides guidance for AI agents working with this repository.

## Repository Overview

This repository contains a **CAS MSED Transfer Thesis** project with two main components:

| Directory | Purpose |
|-----------|---------|
| `thesis/` | LaTeX thesis document |
| `poc/` | Proof of Concept implementation (Python/uv workspace) |

## Thesis (`thesis/`)

LaTeX document for the academic thesis.

### Building
A GitHub Actions workflow at `.github/workflows/build-pdf.yml` builds the PDF automatically.

### Key Files
- `thesis/main.tex` - Main LaTeX document

## Proof of Concept (`poc/`)

Python-based chatbot using MCP (Model Context Protocol) servers.

**See [`poc/AGENTS.md`](poc/AGENTS.md) for detailed PoC development guidance.**

### Quick Reference
```bash
cd poc
uv sync --all-extras           # Install dependencies
uv run pytest                  # Run tests
uv run ty check                # Type checking
uv run ruff check .            # Linting
docker compose up --build      # Run in Docker
```

### Structure
```
poc/
├── apps/
│   ├── chatbot/               # Chatbot application
│   └── mcp_server/            # MCP Server application
├── docker/                    # Dockerfiles per service
├── pyproject.toml             # Workspace root config
└── docker-compose.yml         # Container orchestration
```

## CI/CD Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `.github/workflows/build-pdf.yml` | Push/PR to main | Build thesis PDF |
| `.github/workflows/poc-ci.yml` | Changes to `poc/**` | Lint, type check, test PoC |

## Development Guidelines

- **Python:** 3.14+, managed via `uv`
- **Package Manager:** uv (installed via pipx)
- **Code Quality:** Ruff (lint/format), ty (type check), pre-commit hooks
- **Testing:** pytest
- **Containers:** Docker Compose
