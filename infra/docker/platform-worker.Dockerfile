FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --project apps/platform-worker --frozen --no-dev
RUN groupadd --system platform-worker && \
    useradd --system --gid platform-worker --home-dir /app --no-create-home platform-worker && \
    chown -R platform-worker:platform-worker /app
USER platform-worker
CMD ["/bin/sh", "/app/infra/docker/platform-worker-entrypoint.sh"]
