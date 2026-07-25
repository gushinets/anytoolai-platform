FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --project apps/platform-api --frozen --no-dev
CMD ["uv", "run", "--project", "apps/platform-api", "--no-sync", "uvicorn", "anytoolai_platform_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
