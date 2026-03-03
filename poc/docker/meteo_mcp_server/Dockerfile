FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
COPY apps/meteo_mcp_server/ ./apps/meteo_mcp_server/

RUN uv sync --no-dev --package meteo-mcp-server

EXPOSE 8081

CMD ["uv", "run", "--package", "meteo-mcp-server", "python", "-m", "meteo_mcp_server.main"]
