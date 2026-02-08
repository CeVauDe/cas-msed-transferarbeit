FROM python:3.14-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace config
COPY pyproject.toml uv.lock* README.md ./

# Copy only the chatbot app
COPY apps/chatbot/ ./apps/chatbot/

# Install dependencies for the chatbot package
RUN uv sync --frozen --no-dev --package chatbot

# Run the chatbot
CMD ["uv", "run", "--package", "chatbot", "python", "-m", "chatbot.main"]
