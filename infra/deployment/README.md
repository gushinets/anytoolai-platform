# Deployment

Covers the Proposal AI public web stack (`web-mirror`, `platform-api`, `platform-worker`,
`postgres`) and the separate credential-free development/CI smoke paths.

## Compose layout

- `docker-compose.yml` — base, shared by dev and prod (services, healthchecks, ports, `depends_on`).
- `docker-compose.override.yml` — dev defaults + hot-reload. Auto-merged by a bare
  `docker compose up` run from this directory, and also passed explicitly by `runner.py`/`make dev-up`.
- `docker-compose.prod.yml` — prod overlay. Never auto-merged; always passed explicitly.
- `docker-compose.live.yml` — live provider profile mounts and worker-only OpenAI/proxy settings.
  `prod-up` selects base + prod + live; `prod-fake-up` selects base + prod only.

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
     `prod-up`/`prod-fake-up`/`prod-status`/`prod-down` (`scripts/agent/runner.py` passes it to `docker compose`
     via `--env-file` — only for prod commands, never for dev, so it can never leak into a dev
     stack even if both happen to be running). Best for a persistent local/server setup where
     re-exporting every shell session is annoying.

`ANYTOOLAI_POSTGRES_PORT` / `ANYTOOLAI_API_PORT` override dev's host ports; they default to a
value derived per git worktree (see `docs/agent/worktree-runtime.md`). **Prod uses a separate
variable, `ANYTOOLAI_PROD_API_PORT`** (default `8000`), specifically so a leftover
`ANYTOOLAI_API_PORT` in your shell from dev work doesn't silently change which port `make prod-up`
binds to or checks. Postgres isn't published to the host in prod at all (see below), so there's no
prod-side Postgres port variable. Production web uses `ANYTOOLAI_PROD_WEB_PORT` (default `3000`).
Both production host ports bind to `127.0.0.1` only.

### Separate stakeholder workflow demo secrets

The public Proposal AI deployment leaves `ANYTOOLAI_DEMO_ACCESS_CODE`,
`ANYTOOLAI_ATOM_LAB_ACCESS_CODE`, and `ANYTOOLAI_LIVE_CANARY_TOKEN` blank. `prod-up` rejects
nonblank values, and the production Compose overlay blanks them in the API container. The
following demo instructions apply to a separate private/dev environment, not this public stack.

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

For a separate private demo, put these values in the operator secret store or a gitignored
environment file; do not put them in the public Proposal AI `.env.prod`.
Never place them in URLs, committed files, frontend source, reverse-proxy logs, screenshots, or
stakeholder messages. Share the access code separately and rotate it after the review window.

Any private access to `/demo` requires HTTPS at the reverse-proxy/load-balancer boundary. DNS,
TLS certificates, firewall rules, OpenAI budget controls, and code rotation are operator-owned;
the repository does not provision them.

### Internal Atom Lab access

The Atom Lab shell is available at `/atom-lab`, but it contains no protected catalog data.
Every data request under `/v1/atom-lab/*` requires `X-Atom-Lab-Access-Code`, compared by the API in
constant time with `ANYTOOLAI_ATOM_LAB_ACCESS_CODE`. A missing or blank server value keeps the data
API fail-closed. This code is separate from `ANYTOOLAI_DEMO_ACCESS_CODE` and is injected only into
`platform-api`; `OPENAI_API_KEY` remains worker-only and the server live token is not sent to the
browser.

Atom Lab run admission has five non-secret, `platform-api`-only operational limits. Their Compose
defaults are `ANYTOOLAI_ATOM_LAB_RUN_BODY_MAX_BYTES=393216`,
`ANYTOOLAI_ATOM_LAB_RUN_INPUT_MAX_BYTES=262144`,
`ANYTOOLAI_ATOM_LAB_RUN_PROMPT_MAX_BYTES=65536`,
`ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT=100`, and
`ANYTOOLAI_ATOM_LAB_RUN_ACTIVE_LIMIT=1`. They bound HTTP payloads and admission counts; they are
technical limits, not guarantees about a selected model's context-window capacity. Set overrides in
the operator environment or gitignored `.env.prod`; never add them to `platform-worker`.

For a closed local check, set the code only in the shell that starts Compose:

```bash
export ANYTOOLAI_ATOM_LAB_ACCESS_CODE='replace-with-a-local-lab-code'
python3 scripts/agent/runner.py dev-up
```

Open the worktree-specific API URL reported by `dev-up` with `/atom-lab` appended. Enter the code in
the page; the page keeps it only in tab memory and sends it as a header. Do not place it in a URL,
committed `.env`, logs, screenshots, or browser storage. Use HTTPS and an internal network gate for
any non-local deployment, distribute the code separately, and rotate it by changing the operator
secret followed by an API restart. Production rollout remains operator-owned and is not performed
by ANY-459.

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

### Local Proposal AI live check

With a real `OPENAI_API_KEY` and working `ANYTOOLAI_LLM_HTTPS_PROXY` supplied only through the
shell or gitignored `infra/compose/.env.live`, run:

```bash
python scripts/agent/runner.py dev-live-up --product proposal_ai
python scripts/agent/runner.py dev-web
```

The first command generates an unmetered live profile, starts the development Compose stack,
and checks the mounted profile in API and worker. The second starts the local web host in a
separate terminal. Run more than ten Proposal AI submissions, check successful live provider
rows in `platform.provider_calls` and Squid CONNECT records, and confirm there is no quota GET
or `429`. Repeat with `dev-live-up --product proposal_ai --quota-mode canonical` and verify
normal quota exhaustion. Stop with `dev-down`; a later ordinary `dev-up` uses the canonical
fake-backed product configuration again. Do not treat a successful local web render as proof
of an OpenAI call without the ledger and Squid evidence.

## Prod

Install Docker Engine with the Compose plugin, Python 3.12, and `uv` on the VPS. Clone this
repository at the reviewed deployment commit. Run `python scripts/agent/runner.py doctor`,
`python scripts/agent/runner.py quick-check`, and `uv sync --frozen --group dev` once before
deployment. Use `python3` wherever the host exposes Python 3 under that name.

Copy `infra/compose/.env.example` to gitignored `infra/compose/.env.prod`. Fill the PostgreSQL
user/password/database, a real `OPENAI_API_KEY`, the Squid URL in
`ANYTOOLAI_LLM_HTTPS_PROXY`, `ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai`,
`ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai`, and an explicit
`ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT` chosen from available VPS RAM (the sample is `768M`, not a
measured minimum). Keep all three public access-code variables blank. The shell overrides the
file even with an empty value. An explicitly empty `ANYTOOLAI_UNMETERED_PRODUCT_IDS` selects the
canonical quota; omitting the variable is an error. Never commit or print the completed file.

Before startup, confirm Squid allows `CONNECT api.openai.com:443`; optional cold model-catalog
refresh also reaches `raw.githubusercontent.com:443`. Ensure the worker can reach Squid. Docker
pull/build proxy configuration is separate from the worker's runtime `HTTPS_PROXY`. Runtime
proxy variables alone do not prevent direct egress: enforce worker-to-Squid-only outbound
traffic in the VPS firewall when bypass must be impossible.

```bash
python scripts/agent/runner.py prod-up
python scripts/agent/runner.py prod-status
```

Inspect the printed `Enabled products: proposal_ai` and `Quota modes:
proposal_ai=unmetered` before Compose starts. `prod-up` generates an ignored deployment profile,
then starts base + prod + live Compose, waits for API and web HTTP, and checks the same mounted
profile fingerprint and policy references inside API and worker. It never falls back to fake.
`prod-ready` repeats the live readiness check. `prod-fake-up` is reserved for the credential-free
`kernel_demo` smoke in CI; `prod-smoke` tests that smoke stack, not OpenAI.

The operator-owned Nginx/Caddy instance terminates HTTPS and forwards the product domain to
`127.0.0.1:${ANYTOOLAI_PROD_WEB_PORT:-3000}`. Before its catch-all forward, deny `/atom-lab`,
`/atom-lab/*` (including its CSS/JS), `/v1/atom-lab/*`, and `/v1/demo/*`. Next.js forwards all
`/v1/*` paths to the private API, so those denies must precede the forward. API and web bind
only to loopback; PostgreSQL has no host port. Keep the reverse-proxy config and firewall rules
outside this repository and record their locations with the acceptance evidence.

If Squid intercepts TLS, add an operator-owned Compose override after the live overlay, for
example:

```yaml
services:
  platform-worker:
    environment:
      SSL_CERT_FILE: /run/secrets/squid-ca.pem
    volumes:
      - type: bind
        source: /operator/secrets/squid-ca.pem
        target: /run/secrets/squid-ca.pem
        read_only: true
```

Do not commit the CA or override containing an operator path. A normal CONNECT tunnel needs no
custom CA. For an override, use an operator-owned Compose invocation that includes base, prod,
live, then this file; preserve the same required environment and profile mount.

### Acceptance and quota switch

1. Open the public product domain and run Proposal AI. Confirm another registered product is
   absent from the home page and its direct page shows not found. Direct API runtime-config,
   quota, and scenario-start calls for that disabled product must return safe `404`.
2. From outside the VPS, verify API/web/PostgreSQL ports are not reachable directly. Confirm the
   four denied path groups above are blocked by the inbound proxy and the three API access codes
   are blank. Inspect container environment **by variable name/presence only**: worker has the
   OpenAI key and proxy; API/web do not. Do not dump environment values into evidence.
3. Keep the generated manifest fingerprint as the expected value and run `prod-ready`; its
   read-only check must pass separately in API and worker. Submit more than ten unmetered runs.
   Confirm successful `platform.provider_calls` rows use the live provider policy and that Squid
   logs corresponding CONNECT requests. Confirm `platform.guest_quota_usage` does not gain or
   decrement Proposal AI rows during this window. Save redacted IDs/timestamps, not prompts or
   secrets.
4. Record peak worker memory with `docker stats --no-stream` during a cold catalog refresh and
   real run. Check `docker inspect` for `RestartCount=0` and `OOMKilled=false`; retain memory
   headroom when choosing the production limit.
5. To enable canonical anonymous quota, set `ANYTOOLAI_UNMETERED_PRODUCT_IDS=` in `.env.prod`
   (and remove any exported override), then rerun `prod-up`. Verify a guest with pre-window
   quota rows retains its count; a guest first seen unmetered begins at zero. The web image need
   not change for quota mode alone; runtime config supplies the quota summary.

Rollback to the previously reviewed image/Compose revision and rerun `prod-up` with its matching
environment. For an emergency shutdown, `python scripts/agent/runner.py prod-down` stops the
project without deleting the PostgreSQL volume. Removing the live overlay alone is **not** a
live deployment; use `prod-fake-up` only for the explicit credential-free smoke path.

The production project name is fixed as `anytoolai-prod`. Migrations run once in `migrate` before
API and worker. API stays at one replica while the demo's process-local gate exists, even though
the public deployment denies demo routes. `platform-worker` has an explicit CPU/memory limit;
measure it on the target VPS before treating the sample value as adequate.

## Verifying end-to-end

`*-ready` and `*-smoke` prove two different things, and both are needed to actually trust that a
Compose config boots — not just that it's syntactically valid:

- **`dev-ready`** polls API health. **`prod-ready`** also polls web and runs read-only
  effective-profile checks in API and worker; it does not prove a real OpenAI call succeeded.
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
`compose-smoke-prod` boots `prod-fake-up` with disposable test credentials and `kernel_demo`,
runs `prod-smoke`, then tears down. The public `prod-up` path is live-only.

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

- `infra/compose/docker-compose.agent.yml` — a separate, unrelated compose file (fixed port,
  `anytoolai_agent` database), not wired into `runner.py`/`Makefile`; untouched.
- `.github/workflows/backend.yml`'s Postgres service credentials, and the hardcoded credential
  examples in `docs/architecture/runtime-storage.md` and
  `docs/exec-plans/active/a13-postgresql-concurrency-and-ce-scope.md` — CI config and docs for
  manual test invocations, untouched by this compose split.
