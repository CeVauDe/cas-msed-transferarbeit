FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
COPY apps/meteo_chatbot/ ./apps/meteo_chatbot/

RUN uv sync --no-dev --package meteo-chatbot

EXPOSE 7860

CMD ["uv", "run", "--package", "meteo-chatbot", "python", "-m", "meteo_chatbot.main"]
