# No HEALTHCHECK on purpose (Trivy DS-0026, accepted in ANY-726): the worker has no HTTP surface
# or heartbeat, a process/`SELECT 1` probe would not prove it is consuming jobs, and nothing acts
# on `unhealthy`. Lost jobs are recovered by lease + reconciliation; `*-smoke` proves liveness.
# Add one together with a poll-loop heartbeat. See infra/deployment/README.md "Health checks".
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN uv sync --project apps/platform-worker --frozen --no-dev
RUN groupadd --system platform-worker && \
    useradd --system --gid platform-worker --home-dir /app --no-create-home platform-worker && \
    chown -R platform-worker:platform-worker /app
USER platform-worker
CMD ["/bin/sh", "/app/infra/docker/platform-worker-entrypoint.sh"]
