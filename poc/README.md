# Proof of Concept

This section includes the implementation details of the proof of concept: a chatbot backed by an agent that can use one or more MCP (Model Context Protocol) servers to retrieve information.

## Project Overview

The PoC demonstrates:
- A Python-based chatbot using the Anthropic Claude API
- Integration with MCP servers for tool execution
- Docker Compose setup for easy deployment
- Code quality enforcement with pre-commit hooks and CI/CD

## Prerequisites

- **uv** (installed via pipx): `pipx install uv`
- **Python 3.14+** (installed via uv, if not already available): `uv python install 3.14`
> Do not use Python 3.14 as system default, if it is not already your defauls system python version. This will mess up you system and can even break it!
- **Docker** and **Docker Compose**
- **Git**

## Project Structure

```
poc/
├── docker/
│   ├── chatbot/
│   │   └── Dockerfile          # Chatbot Docker image
│   └── mcp_server/
│       └── Dockerfile          # MCP server Docker image
├── src/
│   ├── chatbot/
│   │   ├── __init__.py         # Chatbot package init
│   │   └── main.py             # Chatbot main entry point
│   └── mcp_server/
│       ├── __init__.py         # MCP server package init
│       └── main.py             # MCP server entry point
├── tests/
│   ├── __init__.py             # Tests package init
│   ├── test_main.py            # Tests for main module
│   └── test_mcp_server.py      # Tests for MCP server
├── .dockerignore               # Docker build ignore rules
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
├── .pre-commit-config.yaml     # Pre-commit hooks configuration
├── docker-compose.yml          # Docker Compose setup
├── README.md                   # This documentation
└── pyproject.toml              # Project configuration

# Note: GitHub Actions workflow is at repo root: /.github/workflows/poc-ci.yml
```

## Setup Instructions

### 1. Initialize the Project

```bash
# Navigate to the poc directory
cd poc

# Initialize the project with uv (creates virtual environment and installs dependencies)
uv sync --all-extras
```

### 2. Set Up Pre-commit Hooks

```bash
# Install pre-commit hooks
uv run pre-commit install

# (Optional) Run hooks on all files to verify setup
uv run pre-commit run --all-files
```

### 3. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your Anthropic API key
# ANTHROPIC_API_KEY=your-api-key-here
```

### 4. Verify the Setup

```bash
# Run the tests
uv run pytest -v

# Run the chatbot locally
uv run python -m chatbot.main

# Run type checking manually
uv run ty check
```

## Development Workflow

### Running Code Quality Checks

Pre-commit hooks run automatically on `git commit`. To run them manually:

```bash
# Run all hooks on staged files
uv run pre-commit run

# Run all hooks on all files
uv run pre-commit run --all-files

# Run specific hooks
uv run pre-commit run ruff --all-files
uv run pre-commit run ruff-format --all-files
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests with coverage (requires pytest-cov)
uv run pytest --cov=chatbot

# Run specific test file
uv run pytest tests/test_main.py

# Run specific test
uv run pytest tests/test_main.py::TestGreet::test_greet_default
```

### Type Checking

```bash
# Run type checking with ty
uv run ty check
```

### Linting and Formatting

```bash
# Check for linting issues
uv run ruff check src tests

# Auto-fix linting issues
uv run ruff check --fix src tests

# Format code
uv run ruff format src tests

# Check formatting without changes
uv run ruff format --check src tests
```

## Docker Setup

### Building and Running with Docker Compose

```bash
# Build all services
docker compose build

# Start all services
docker compose up

# Start in detached mode
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

### Building Individual Images

```bash
# Build chatbot image
docker build -t mcp-chatbot -f Dockerfile .

# Build MCP server image
docker build -t mcp-server -f Dockerfile.mcp-server .
```

### Running Containers Individually

```bash
# Run chatbot
docker run -it --rm \
  mcp-chatbot

# Run MCP server
docker run -d --rm \
  -p 8080:8080 \
  mcp-server
```

## CI/CD Pipeline

The GitHub Actions workflow (located at repo root: `/.github/workflows/poc-ci.yml`) runs on every pull request and push to `main` that affects files in the `poc/` directory:

### Jobs

1. **lint-and-type-check**: Runs all pre-commit hooks including:
   - Trailing whitespace removal
   - End-of-file fixer
   - YAML/TOML validation
   - Ruff linting and formatting
   - ty type checking

2. **test**: Runs the pytest test suite

### Triggering the Pipeline

The CI pipeline runs automatically on:
- Every push to the `main` branch (when `poc/**` files change)
- Every pull request targeting `main` (when `poc/**` files change)

## Adding Dependencies

```bash
# Add a production dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>

# Update the lock file
uv lock
```

## Common Issues and Solutions

### Pre-commit Hook Failures

If pre-commit hooks fail, they often auto-fix the issues. Simply stage the changes and commit again:

```bash
git add -u
git commit -m "Your message"
```

### Type Checking Errors

ty may report type errors for external libraries without type stubs. You can:
1. Install type stubs: `uv add --dev types-<package>`
2. Add the package to ty's ignore list in `pyproject.toml`

### Docker Build Failures

Ensure `uv.lock` exists before building Docker images:

```bash
uv lock
docker compose build
```

## Next Steps

To extend this PoC:

1. **Implement the MCP server**: Add actual tools and resources to `mcp_server.py`
2. **Build the chatbot agent**: Implement the Claude-based agent in `main.py`
3. **Add more MCP servers**: Create additional servers for different data sources
4. **Enhance tests**: Add integration tests for the full chatbot flow
5. **Add logging**: Implement structured logging with `structlog` or similar
