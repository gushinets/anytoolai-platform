FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --project apps/platform-worker --frozen --no-dev
CMD ["uv", "run", "--project", "apps/platform-worker", "--no-sync", "anytoolai-platform-worker"]
