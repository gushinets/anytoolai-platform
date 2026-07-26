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

`docker-compose.yml` also defines a `migrate` service: a one-shot container (same image as
`platform-api`, `prod` target, entrypoint overridden to run `anytoolai-platform-migrate` and
exit) that applies Alembic migrations to head. `platform-api`/`platform-worker` declare
`depends_on: migrate: condition: service_completed_successfully`, so both wait for it to finish
before starting — and neither one runs migrations itself. See "Migrations and scaling" below.

## Credentials

`ANYTOOLAI_POSTGRES_USER`, `ANYTOOLAI_POSTGRES_PASSWORD`, `ANYTOOLAI_POSTGRES_DB` default to
`anytoolai`/`anytoolai`/`anytoolai` directly in the base file (`docker-compose.yml`'s
`${VAR:-anytoolai}` interpolation) — not in `docker-compose.override.yml`. They have to live in
the base file: Compose interpolates each `-f` file independently before merging, so a
`${VAR:?required}` in the base file would break dev even when an override supplies a default
for the same key:

- **Dev** — picks up the base file's `anytoolai`/`anytoolai`/`anytoolai` default as-is (also
  mirrored by `scripts/agent/runner.py`'s own dev defaults). No setup required to get started.
- **Prod** — required (`${VAR:?...}`). `docker-compose.prod.yml` overrides the same keys to
  refuse starting if any of the three are unset, instead of silently falling back to dev
  credentials. Provide real values from your secret store / CI secrets — never commit them.
  Two ways to supply them, in precedence order (shell wins over the file):
  1. `export ANYTOOLAI_POSTGRES_USER=... ANYTOOLAI_POSTGRES_PASSWORD=... ANYTOOLAI_POSTGRES_DB=...`
     before running `make prod-up` — best for CI or a one-off run.
  2. Copy `infra/compose/.env.example` to `infra/compose/.env.prod` and fill in real values.
     `.env.prod` is gitignored (`.gitignore`'s `.env.*` rule) and picked up automatically by
     `prod-up`/`prod-status`/`prod-down` (`scripts/agent/runner.py` passes it to `docker compose`
     via `--env-file` — only for prod commands, never for dev, so it can never leak into a dev
     stack even if both happen to be running). Best for a persistent local/server setup where
     re-exporting every shell session is annoying.

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
- Migrations run once, via the `migrate` service — not inside `platform-api`/`platform-worker`
  themselves. Both wait for `migrate` to exit successfully before starting (see "Migrations and
  scaling" below).

## Prod

```bash
cp infra/compose/.env.example infra/compose/.env.prod   # fill in real values, once
make prod-up      # docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
make prod-status
make prod-down
```

(Or skip the `.env.prod` file and `export ANYTOOLAI_POSTGRES_USER=... ANYTOOLAI_POSTGRES_PASSWORD=...
ANYTOOLAI_POSTGRES_DB=...` instead — see "Credentials" above.)

- Uses project name `anytoolai-prod` (fixed — unlike dev, prod is not per-worktree).
- `platform-api` builds the `prod` target of the same Dockerfile: dependencies are installed via
  `uv sync --frozen --no-dev` in their own build layer, so no dev-only packages end up in this
  image. No bind-mounts, no `--reload`.
- `deploy.resources.limits` (cpus/memory) are set on all four services, including `migrate`.
  `restart: unless-stopped` is set on the three long-running services (`postgres`,
  `platform-api`, `platform-worker`) only — `migrate` deliberately has no `restart` (Compose's
  default, `no`), since it's a one-shot job that's supposed to exit, not be restarted forever.
- `deploy.replicas: 1` on `platform-api` is only the default replica count, not a safety
  ceiling — see "Migrations and scaling" below for why raising it (or `--scale
  platform-api=N`) is safe.
- Postgres's port is **not** published to the host in prod (unlike dev) — `docker-compose.prod.yml`
  resets the base file's `ports:` mapping to empty, since `platform-api`/`platform-worker` reach it
  over the compose network as `postgres:5432` and don't need it exposed. If an operator genuinely
  needs external access (manual psql/admin), add an explicit `ports:` mapping in a local,
  uncommitted overlay — ideally bound to `127.0.0.1` or restricted at the firewall/security-group
  level rather than published broadly.

## Migrations and scaling

Migrations run in their own one-shot `migrate` service (see "Compose layout" above), not inside
`platform-api`/`platform-worker`. `platform-api`/`platform-worker` `depends_on: migrate:
condition: service_completed_successfully` — Compose won't start either until `migrate` has
exited 0, and neither of them ever runs `alembic upgrade head` itself.

This is what makes running more than one `platform-api` replica safe: there's no migration
code path left inside `platform-api` to race on, regardless of how many containers start
concurrently or how `deploy.replicas` is set. If `migrate` fails (bad migration, unreachable
DB), `platform-api`/`platform-worker` simply never start — checked with `make prod-status` /
`docker compose logs migrate`.

## Explicitly out of scope

- `web-mirror` — dockerization is paused separately.
- `infra/compose/docker-compose.agent.yml` — a separate, unrelated compose file (fixed port,
  `anytoolai_agent` database), not wired into `runner.py`/`Makefile`; untouched.
- `.github/workflows/backend.yml`'s Postgres service credentials, and the hardcoded credential
  examples in `docs/architecture/runtime-storage.md` and
  `docs/exec-plans/active/a13-postgresql-concurrency-and-ce-scope.md` — CI config and docs for
  manual test invocations, untouched by this compose split.
