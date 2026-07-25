# Deployment

Covers `platform-api`, `platform-worker`, `postgres` via `infra/compose/`. `web-mirror` is
intentionally out of scope — its dockerization is paused separately.

## Compose layout

- `docker-compose.yml` — base, shared by dev and prod (services, healthchecks, ports, `depends_on`).
- `docker-compose.override.yml` — dev defaults + hot-reload. Auto-merged by a bare
  `docker compose up` run from this directory, and also passed explicitly by `runner.py`/`make dev-up`.
- `docker-compose.prod.yml` — prod overlay. Never auto-merged; always passed explicitly.

`docker-compose.prod.yml` uses the Compose Specification's `!reset`/`!override` merge tags (to
drop Postgres's host port and fully replace `platform-api`'s). These require a reasonably
recent `docker compose` CLI — tested with v5.3.1 here. If `make prod-up` fails with a YAML
parse error mentioning `!reset` or `!override`, upgrade Docker Compose
(see [Merge Compose files](https://docs.docker.com/reference/compose-file/merge/)).

## Credentials

`ANYTOOLAI_POSTGRES_USER`, `ANYTOOLAI_POSTGRES_PASSWORD`, `ANYTOOLAI_POSTGRES_DB` have no
defaults in the base file:

- **Dev** — defaulted to `anytoolai`/`anytoolai`/`anytoolai` by `docker-compose.override.yml`
  and by `scripts/agent/runner.py`. No setup required to get started.
- **Prod** — required (`${VAR:?...}`). `docker-compose.prod.yml` refuses to start if any of
  the three are unset, instead of silently falling back to dev credentials. Export real values
  from your secret store / CI secrets before running `make prod-up` — never commit them.

`ANYTOOLAI_POSTGRES_PORT` / `ANYTOOLAI_API_PORT` override dev's host ports; they default to a
value derived per git worktree (see `docs/agent/worktree-runtime.md`). **Prod uses a separate
variable, `ANYTOOLAI_PROD_API_PORT`** (default `8000`), specifically so a leftover
`ANYTOOLAI_API_PORT` in your shell from dev work doesn't silently change which port `make prod-up`
binds to or checks. Postgres isn't published to the host in prod at all (see below), so there's no
prod-side Postgres port variable.

## Dev

```bash
make dev-up      # build + start postgres/platform-api/platform-worker
make dev-ready   # poll until platform-api /health is up
make dev-status  # docker compose ps
make dev-down    # tear down
```

- `platform-api` builds the `dev` target of `infra/docker/platform-api.Dockerfile`: source
  under `apps/platform-api/src` and `packages/backend/platform-core/src` is bind-mounted into
  the container, and uvicorn runs with `--reload` — edits on the host trigger an automatic
  reload, no rebuild needed.
- Migrations run automatically on every `platform-api` container start
  (`infra/docker/platform-api-entrypoint.sh` runs `anytoolai-platform-migrate` before starting
  uvicorn). `platform-worker` waits for `platform-api` to become healthy before starting, so it
  never races ahead of the schema.

## Prod

```bash
export ANYTOOLAI_POSTGRES_USER=...
export ANYTOOLAI_POSTGRES_PASSWORD=...
export ANYTOOLAI_POSTGRES_DB=...
make prod-up      # docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
make prod-status
make prod-down
```

- Uses project name `anytoolai-prod` (fixed — unlike dev, prod is not per-worktree).
- `platform-api` builds the `prod` target of the same Dockerfile: dependencies are installed via
  `uv sync --frozen --no-dev` in their own build layer, so no dev-only packages end up in this
  image. No bind-mounts, no `--reload`.
- `restart: unless-stopped` and `deploy.resources.limits` (cpus/memory) are set on all three services.
- **Do not scale `platform-api` beyond one instance.** `docker-compose.prod.yml` sets
  `deploy.replicas: 1`, but this is documentation of intent, not an enforced limit — plain
  `docker compose` (outside Swarm mode) does not actually enforce `deploy.replicas`, and
  `docker compose ... up --scale platform-api=2` silently overrides it. Migrations run from
  `platform-api`'s own entrypoint on every container start (idempotent — `alembic upgrade head`
  checks the current schema version and is a no-op once the database is already at head). The
  real risk window is narrow but concrete: if two containers start at nearly the same moment
  while the database is *not yet* at head (e.g. during a rollout that introduces a new
  migration), both will try to apply the same pending migration concurrently, racing on
  `alembic_version`/DDL locks. Scaling `platform-api` beyond one replica safely requires first
  moving migrations into a separate, coordinated step (a one-shot job, or a lock around the
  migration) — not implemented today; this is the operational constraint that stands in for it.
- Postgres's port is **not** published to the host in prod (unlike dev) — `docker-compose.prod.yml`
  resets the base file's `ports:` mapping to empty, since `platform-api`/`platform-worker` reach it
  over the compose network as `postgres:5432` and don't need it exposed. If an operator genuinely
  needs external access (manual psql/admin), add an explicit `ports:` mapping in a local,
  uncommitted overlay — ideally bound to `127.0.0.1` or restricted at the firewall/security-group
  level rather than published broadly.

## Explicitly out of scope

- `web-mirror` — dockerization is paused separately.
- `infra/compose/docker-compose.agent.yml` — a separate, unrelated compose file (fixed port,
  `anytoolai_agent` database), not wired into `runner.py`/`Makefile`; untouched.
- `.github/workflows/backend.yml`'s Postgres service credentials, and the hardcoded credential
  examples in `docs/architecture/runtime-storage.md` and
  `docs/exec-plans/active/a13-postgresql-concurrency-and-ce-scope.md` — CI config and docs for
  manual test invocations, untouched by this compose split.
