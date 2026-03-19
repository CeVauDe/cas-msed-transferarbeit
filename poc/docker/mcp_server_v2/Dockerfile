# ============================================================
# Stage 1: Download raw data and transform to Parquet (v2)
# ============================================================
FROM python:3.14-slim AS data-builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

# Copy workspace config for dependency resolution
COPY pyproject.toml uv.lock README.md ./
COPY apps/chatbot/pyproject.toml ./apps/chatbot/pyproject.toml
COPY apps/mcp_server/pyproject.toml ./apps/mcp_server/pyproject.toml

# Install deps including dev (pandas, openpyxl, pyarrow)
RUN uv sync --package mcp-server

# Copy only the data pipeline scripts
COPY apps/mcp_server/src/tools/ ./apps/mcp_server/src/tools/

# Download raw Excel files from GitHub Release and transform to v2 Parquet
RUN uv run --package mcp-server python apps/mcp_server/src/tools/download_data.py \
 && uv run --package mcp-server python apps/mcp_server/src/tools/load_jahresbericht_v2.py

# ============================================================
# Stage 2: Production image
# ============================================================
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace config
COPY pyproject.toml uv.lock README.md ./

# Copy workspace stubs for other members so uv can resolve the workspace
COPY apps/chatbot/pyproject.toml ./apps/chatbot/pyproject.toml

# Copy only the mcp-server app (includes both mcp_server and mcp_server_v2)
COPY apps/mcp_server/ ./apps/mcp_server/

# Overlay the generated v2 Parquet from the build stage
COPY --from=data-builder /build/apps/mcp_server/data/Jahresbericht_v2.parquet \
     ./apps/mcp_server/data/Jahresbericht_v2.parquet

# Install production dependencies
RUN uv sync --no-dev --package mcp-server

EXPOSE 8081

CMD [".venv/bin/python", "-m", "mcp_server_v2.main"]
