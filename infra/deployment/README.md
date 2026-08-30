# Deployment

Covers `platform-api`, `platform-worker`, `postgres` via `infra/compose/`. The stakeholder
workflow demo is served directly by `platform-api`; the separate `web-mirror` application is
still intentionally out of scope and its dockerization remains paused.

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

### Stakeholder workflow demo secrets

The Russian-language stakeholder surface is available at `/demo`. Loading the page is public,
but `POST /v1/demo/runs` fails closed unless all runtime credentials are configured:

- `ANYTOOLAI_DEMO_ACCESS_CODE` is provided only to `platform-api` and compared with the request's
  `X-Demo-Access-Code` header using a constant-time comparison;
- in deployed services, `ANYTOOLAI_LIVE_CANARY_TOKEN` is injected only into `platform-api`, which
  uses it server-side when starting one of the three allowlisted internal live scenarios;
- in deployed services, `OPENAI_API_KEY` is injected only into `platform-worker`, where Provider
  Gateway performs the real model call.

Repository-operated Compose and live-canary workflows have a separate operator/CI boundary:
the shell or CI steps that run `dev-up` and `live-canary` must provide both
`ANYTOOLAI_LIVE_CANARY_TOKEN` and `OPENAI_API_KEY`. Compose reads them while creating the two
service containers, and `scripts/agent/runner.py live-canary` reads them for its fail-fast checks.
Neither value is sent to the demo frontend.

Put these values in the operator secret store or the gitignored `infra/compose/.env.prod` file.
Never place them in URLs, committed files, frontend source, reverse-proxy logs, screenshots, or
stakeholder messages. Share the access code separately and rotate it after the review window.

Production access to `/demo` requires HTTPS at the reverse-proxy/load-balancer boundary. DNS,
TLS certificates, firewall rules, OpenAI budget controls, and code rotation are operator-owned;
the repository does not provision them.

### Run the stakeholder page locally

Start Docker Desktop, then run the worktree-aware development stack from the repository root:

```bash
python scripts/agent/runner.py dev-up
```

The command prints the derived API URL for this checkout. Open that URL with `/demo` appended,
for example `http://127.0.0.1:18123/demo`. Do not assume port 8000: recover the exact URL at any
time with:

```bash
python scripts/agent/runner.py dev-status
```

This is sufficient to inspect the page. Workflow starts remain fail-closed until the three
runtime values are present in the shell that launches Compose. To exercise the real AI chains,
set them before `dev-up`:

```bash
export ANYTOOLAI_DEMO_ACCESS_CODE='replace-with-a-local-shared-code'
export ANYTOOLAI_LIVE_CANARY_TOKEN='replace-with-a-local-live-token'
export OPENAI_API_KEY='replace-with-a-real-provider-key'
python scripts/agent/runner.py dev-up
```

Enter the value of `ANYTOOLAI_DEMO_ACCESS_CODE` on the page. Stop this checkout's stack with
`python scripts/agent/runner.py dev-down`. On systems where Python 3 is exposed only as
`python3`, use `python3` in the commands above.

## Dev

```bash
make dev-up      # build + start postgres/platform-api/platform-worker (waits for dev-ready)
make dev-ready   # poll until platform-api /health is up
make dev-status  # docker compose ps
make dev-smoke   # prove platform-worker is actually processing jobs (see "Verifying end-to-end")
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
make prod-up      # docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build (waits for prod-ready)
make prod-ready   # poll until platform-api /health is up
make prod-status
make prod-smoke   # prove platform-worker is actually processing jobs (see "Verifying end-to-end")
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
- `deploy.replicas: 1` on `platform-api` is a safety ceiling while `/demo` is exposed. The demo
  gate combines durable PostgreSQL counts with one process-local check-and-start lock; multiple
  replicas could both accept a start. Replace it with a PostgreSQL advisory lock before raising
  the replica count. Migration execution itself remains replica-safe as described below.
- Postgres's port is **not** published to the host in prod (unlike dev) — `docker-compose.prod.yml`
  resets the base file's `ports:` mapping to empty, since `platform-api`/`platform-worker` reach it
  over the compose network as `postgres:5432` and don't need it exposed. If an operator genuinely
  needs external access (manual psql/admin), add an explicit `ports:` mapping in a local,
  uncommitted overlay — ideally bound to `127.0.0.1` or restricted at the firewall/security-group
  level rather than published broadly.

## Verifying end-to-end

`*-ready` and `*-smoke` prove two different things, and both are needed to actually trust that a
Compose config boots — not just that it's syntactically valid:

- **`dev-ready` / `prod-ready`** poll `platform-api`'s `/health` endpoint. This proves
  `platform-api` itself came up and is answering HTTP requests — nothing more.
- **`dev-smoke` / `prod-smoke`** drive real jobs through the stack via
  `scripts/agent/kernel_demo_smoke.py`: for each of the 11 kernel_demo standalone atom
  scenarios (`ATOM_SMOKE_CASES`, one per generic action type), create a fresh guest identity,
  start the scenario (its action config uses the fake provider, so this makes no external calls
  and needs no API keys), then poll until it completes, reporting an explicit `N/11` result. This
  is the only thing that proves **`platform-worker`** is actually healthy — it has no Docker
  healthcheck and no HTTP surface of its own (`infra/docker/platform-worker.Dockerfile` is a
  plain DB-polling loop with no `healthcheck:` in `docker-compose.yml`), so `docker compose ps`
  reporting it as "running" only means the process hasn't crashed, not that it's consuming jobs
  from the queue. A stopped or wedged `platform-worker` (`docker compose stop platform-worker`)
  makes `*-smoke` fail with a clear `SMOKE00x` error instead of hanging or silently reporting
  success -- every remaining case still runs rather than aborting on the first timeout (so a
  genuinely broken single atom isn't hidden behind an unrelated outage), but the per-case
  timeout degrades to a short probe after the first real timeout, so a full outage still
  reports failure well before `N * --timeout`.

`kernel_demo_smoke.py` is a standalone script (same `argparse`/`main()` convention as
`validate_configs.py`), so it can also be run directly against any reachable `platform-api`:
`python scripts/agent/kernel_demo_smoke.py http://127.0.0.1:8000`.

CI runs both legs on every PR, as two independent parallel jobs in
`.github/workflows/backend.yml`: `compose-smoke-dev` boots dev, runs `dev-smoke`, tears down;
`compose-smoke-prod` boots prod with disposable test credentials, runs `prod-smoke`, tears down.

## Migrations and scaling

Migrations run in their own one-shot `migrate` service (see "Compose layout" above), not inside
`platform-api`/`platform-worker`. `platform-api`/`platform-worker` `depends_on: migrate:
condition: service_completed_successfully` — Compose won't start either until `migrate` has
exited 0, and neither of them ever runs `alembic upgrade head` itself.

This makes application startup and schema migration safe for more than one `platform-api`
replica: there is no migration code path left inside the API containers to race. It does not
make every application-level coordination primitive distributed. In particular, the stakeholder
`/demo` busy/daily check currently requires exactly one API replica; replace its process lock with
a PostgreSQL advisory lock before scaling the API while that route is enabled. If `migrate` fails
(bad migration, unreachable DB), `platform-api`/`platform-worker` simply never start — checked
with `make prod-status` / `docker compose logs migrate`.

## Verifying the stakeholder demo

After configuring HTTPS and the three secrets above:

1. Open `https://<host>/demo` outside the operator's local network.
2. Enter the separately shared demo access code and complete one workflow.
3. Verify the result view contains real `scenario_session_id`, `job_id`,
   `result_artifact_id`, and `workflow_id` values.
4. Send a request with a wrong code and verify it receives `401 demo_access_denied` without a
   new row in `platform.scenario_sessions`.
5. Confirm a second start while the first job is `created` or `running` receives `409 demo_busy`.

The backend job is not canceled if the browser's 90-second polling window expires. Inspect the
existing runtime rows and worker logs by technical ID instead of starting a duplicate run.

## Explicitly out of scope

- `web-mirror` — dockerization is paused separately.
- `infra/compose/docker-compose.agent.yml` — a separate, unrelated compose file (fixed port,
  `anytoolai_agent` database), not wired into `runner.py`/`Makefile`; untouched.
- `.github/workflows/backend.yml`'s Postgres service credentials, and the hardcoded credential
  examples in `docs/architecture/runtime-storage.md` and
  `docs/exec-plans/active/a13-postgresql-concurrency-and-ce-scope.md` — CI config and docs for
  manual test invocations, untouched by this compose split.
