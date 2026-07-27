# NOTE: this image uses ENTRYPOINT (not CMD) to always run the entrypoint script.
# `docker run <image> <args>` no longer replaces the process the way it would with a plain
# CMD — <args> get appended to the entrypoint script's "$@" (and from there to uvicorn's own
# args) instead. There's no existing `docker run <image> <alt-command>` usage in this repo to
# worry about breaking, but keep this in mind if you ever add one.
#
# This same image (prod target) also backs the `migrate` compose service, which overrides
# ENTRYPOINT to run `anytoolai-platform-migrate` directly instead of this script -- see
# docker-compose.yml. Alembic/psycopg are main dependencies (not dev-only), so both targets
# can run migrations.
FROM ghcr.io/astral-sh/uv:0.11.19 AS uv-bin

FROM python:3.12-slim AS base
COPY --from=uv-bin /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN chmod +x infra/docker/platform-api-entrypoint.sh

FROM base AS dev
RUN uv sync --project apps/platform-api --frozen --group dev
ENTRYPOINT ["/app/infra/docker/platform-api-entrypoint.sh", "--reload"]

FROM base AS prod
RUN uv sync --project apps/platform-api --frozen --no-dev
RUN groupadd --system platform-api && \
    useradd --system --gid platform-api --home-dir /app --no-create-home platform-api && \
    chown -R platform-api:platform-api /app
USER platform-api
ENTRYPOINT ["/app/infra/docker/platform-api-entrypoint.sh"]