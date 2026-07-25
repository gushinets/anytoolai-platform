# NOTE: this image uses ENTRYPOINT (not CMD) to always run migrations before uvicorn starts.
# `docker run <image> <args>` no longer replaces the process the way it would with a plain
# CMD — <args> get appended to the entrypoint script's "$@" (and from there to uvicorn's own
# args) instead. There's no existing `docker run <image> <alt-command>` usage in this repo to
# worry about breaking, but keep this in mind if you ever add one.
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv
WORKDIR /app
COPY . .
RUN chmod +x infra/docker/platform-api-entrypoint.sh

FROM base AS dev
RUN uv sync --project apps/platform-api --frozen --group dev
ENTRYPOINT ["infra/docker/platform-api-entrypoint.sh", "--reload"]

FROM base AS prod
RUN uv sync --project apps/platform-api --frozen --no-dev
ENTRYPOINT ["infra/docker/platform-api-entrypoint.sh"]