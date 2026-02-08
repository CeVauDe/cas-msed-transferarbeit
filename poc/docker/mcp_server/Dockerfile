FROM python:3.14-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace config
COPY pyproject.toml uv.lock* README.md ./

# Copy only the mcp-server app
COPY apps/mcp_server/ ./apps/mcp_server/

# Install dependencies for the mcp-server package
RUN uv sync --frozen --no-dev --package mcp-server

EXPOSE 8080

# Run the MCP server
CMD ["uv", "run", "--package", "mcp-server", "python", "-m", "mcp_server.main"]
