# Deployment

Covers the public product stack, the separate Atom Lab stack, and credential-free development
and CI smoke checks. Start a VPS update with the [VPS release runbook](vps-release-runbook.md).

## Reviewed images and independent updates (ANY-766 Step 17)

The optional `docker-compose.images.yml` selects `ANYTOOLAI_API_IMAGE` (also the
migration image), `ANYTOOLAI_WORKER_IMAGE` and `ANYTOOLAI_WEB_IMAGE`. It removes
build contexts and never pulls. `prod-up` opts in when `ANYTOOLAI_API_IMAGE` is
set, including through the existing private `.env.prod`; all three refs must be
versioned tags or immutable digests. API and worker require identical nonempty
`org.opencontainers.image.revision` labels. This is necessary source evidence,
not a universal wire or data compatibility declaration. Use the matching reviewed
control checkout; old binaries are excluded from the ANY-766 synchronized API
cutover. The
[Portal paired cutover procedure](https://github.com/gushinets/payments-portal/blob/main/docs/architecture/deployment.md#paired-compatibility-and-synchronized-cutover)
owns the migration order and purchased-document reader floor.

`.github/workflows/publish-images.yml` builds `backend` (API and worker),
`frontend` or `all` independently. Publishing is default-off and requires separate
post-review authorization. Frontend inputs are `PLATFORM_API_BASE_URL` (the
build-time same-origin rewrite destination),
`NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS`, `ANYTOOLAI_WEB_BASE_PATH` and
`NEXT_PUBLIC_PORTAL_AUTHORIZE_URL` (localized Portal `/backend/authorize` URL).
Changing runtime variables cannot recompile these values. Public frontend image
tags include the run ID to distinguish builds with different origins. Backend
credentials and provider secrets are runtime-only.

For an operator-approved installation, set private `.env.prod` credentials and
selected images plus `ANYTOOLAI_PROFILE_ROOT` to an existing operator-owned
absolute host directory. The candidate profile is generated **inside the selected
API image**, with only that directory mounted at `/deployment`, network disabled
and dependency synchronization disabled. The host mount paths are derived from
the explicit host directory, never from `/app` or `/deployment` container paths.
Both selected backend images must match the candidate source fingerprint; existing
profile checks verify the mounted result in running API and worker. Existing
activation marker semantics remain unchanged: the worker waits for activation,
API admission remains closed, and the previous profile is retained until success.
Migration/readiness/activation failure keeps admission closed and retains volumes.

```bash
# Optional explicit selection for a disposable local rehearsal or another approved
# installation; defaults remain infra/compose/.env.prod and anytoolai-prod.
export ANYTOOLAI_PROD_ENV_FILE=/operator/kernel/images.env
export ANYTOOLAI_PROD_PROJECT=anytoolai-prod
# The env file includes ANYTOOLAI_*_IMAGE and ANYTOOLAI_PROFILE_ROOT.
# Pull reviewed digests separately, only with registry/publication authorization.
./.quick-check-venv/bin/python scripts/agent/runner.py prod-up
./.quick-check-venv/bin/python scripts/agent/runner.py prod-ready
# Replace only web; no migration, backend restart or profile generation/activation.
./.quick-check-venv/bin/python scripts/agent/runner.py prod-web-up
```

Image `prod-up` uses the existing shared deployment lock and, for an existing
stack, existing `prod-quiesce` (stop admission, drain all jobs, stop worker).
It starts retained PostgreSQL, runs a fresh one-shot migration from the selected
API image, then starts the selected API/worker/web without builds or pulls.
All other producers and deployment automation must remain stopped throughout the
operator's maintenance window. Failure to drain does not stop the recovering
worker. On migration failure, do not run old code to reopen service. Follow the
existing verified backup recovery below and the metering cutover safeguards.

The concrete ANY-766 pair uses Kernel head `0021`, Portal `20261111_0011`,
identity V2, snapshot V3 and manifest/invalidation/usage/exhaustion V1. Kernel
source baseline is `88da001f0595a4bc8e4729423acd2340bf7b73ca`, Portal
`0b1cbfa310c02aee182a75aaf7608fc587266a67`, plus the reviewed Step 17 diff.
Record actual reviewed SHAs, image IDs/digests, build origins, enabled products
and base path with the environment selection. Never infer reader compatibility
from unchanged migration heads: Portal pre-selected-digest and pre-Step-11
purchase readers are excluded, as are old Kernel identity/snapshot binaries.
Keep historical usage, reservations, floors and purchased documents intact.

This Linux image path does not require a remote server or registry credentials
for local images. Use disposable databases and loopback test origins for rehearsal.
Remote publication, installation, secrets, backups, live-service acceptance and
remaining broad suites are deferred to ANY-767. The focused Step 16 HTTP/browser
proof remains valid for unchanged runtime code; packaging checks do not replace
later deployed acceptance.

### Local image build inputs

Linux builds on 2026-11-11 used Docker Engine 28.1.1 / Compose 2.35.1. The actual
selected pre-review local IDs (no registry publication/digests) are:

- `any766-step17/kernel-api:local` — `sha256:50b612d750e720b088ae76c71af57768f0fdfe7fed69d572367ed8d98a39a563`.
- `any766-step17/kernel-worker:local` — `sha256:a5727020048d209d7bf7bb0bd84531e2f85d526c6b808e78f1101af2533e8a77`.
- `any766-step17/kernel-web:install-verified` — `sha256:e8ad25d1bda7d5ade18b7fe14420daa02295b24ed9959cefe6169f8b7fcdc880`.

API target: `infra/docker/platform-api.Dockerfile`, `prod`; worker uses its existing
Dockerfile and locked project. Both revision labels use the source baseline above
with `-step17-local`. The matching controller includes local Step 17 corrections;
reviewed source SHAs/digests must be recorded after review. No application source,
purchased-document or wire migration was added in this packaging step.
Web inputs: `PLATFORM_API_BASE_URL=http://platform-api:8000`,
`NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai`,
`ANYTOOLAI_WEB_BASE_PATH=/tools`,
`NEXT_PUBLIC_PORTAL_AUTHORIZE_URL=https://portal.step17.example.test/ru/backend/authorize`.
The HTTPS test name is only a build input; ingress/TLS is not installed by rehearsal.

The profile directory must belong to the operator, have no group/world write
permission (for example 0755) and contain only this installation's non-secret
profiles. Profile generation uses the operator UID and a temporary `uv` cache
inside the selected container, with `--no-sync` and no network. The optional
existing `LITELLM_LOCAL_MODEL_COST_MAP` variable is passed through the image
override for offline rehearsal; absent values preserve normal library behavior.
Local rehearsal uses its bundled map and a loopback-only provider proxy rather
than contacting OpenAI/metadata services. Kernel's normal network is retained
for real loopback port publication; on the tested Engine, Docker `internal`
networks suppress that publication and prevent the host-side readiness check. Portal's
separate private networks and both database volumes remain independent.

The disposable image rehearsal passed all nine cases across the pair: initial
installation, production web HTTP and compiled origins, frontend-only replacement
with unchanged backend/DB container identities and profile marker, retained
synthetic identity/usage after backend/container recreation, both non-root
backend users reading the activation marker, and both actual failing-migration
recovery paths. Kernel's failed candidate left the prior profile/marker intact
and admission closed; restoring the selected images retained data at head `0021`
(Portal `20261111_0011`). Candidate source fingerprint was
`c52ae82cf1dd5fa54db6c809ea0ddc652c38dea966c3517ac00eac23b7720dce`,
profile fingerprint `ad79b2bf92ce569d241e06c42ffbbb6918cf3e6998108ae46a770f06f2cb2f6b`.
All run-owned containers, networks and volumes were removed. The required runner
suite retains one host-environment failure: passwordless `sudo -u nobody` is
unavailable; actual container marker access passed. No live provider, production
data, registry publication or remote installation was involved.

## Compose layout

- `docker-compose.yml` — base, shared by dev and prod (services, ports, `depends_on`; app
  healthchecks live in the images, see "Health checks" below).
- `docker-compose.override.yml` — dev defaults + hot-reload. Auto-merged by a bare
  `docker compose up` run from this directory, and also passed explicitly by `runner.py`/`make dev-up`.
- `docker-compose.prod.yml` — prod overlay. Never auto-merged; always passed explicitly.
- `docker-compose.live.yml` — live provider profile mounts and worker-only OpenAI/proxy settings.
  `prod-up` selects base + prod + live; `prod-fake-up` selects base + prod only.
- `docker-compose.atom-lab.yml` — private Atom Lab overlay over the base services: durable
  PostgreSQL, loopback-only ports, required Lab/live/provider secrets, and no public web service.
- `docker-compose.vps-135.yml` — optional occupied-host network overlay. Setting
  `ANYTOOLAI_VPS_135_NETWORKS=1` makes live `prod-up`/`prod-ready` append it: only
  `platform-worker` joins external `infra_prompttune`, and only `web-mirror` joins external
  `payments-portal-prod_edge`; both retain the AnytoolAI default network. The web build uses
  `platform-api.anytoolai-prod_default` to reach the product API even when Lab shares the edge
  network. Run containers under the fixed `anytoolai-prod` project with this overlay. Other
  selector values fail before Compose starts. Fake and dev commands never select this overlay.
- `docker-compose.atom-lab.vps-135.yml` — Atom Lab network overlay selected by
  `ANYTOOLAI_VPS_135_NETWORKS=1` in the Lab environment. The API joins the Caddy edge network
  as `atom-lab-api` and the worker joins `infra_prompttune` for the provider proxy.

`docker-compose.prod.yml` and `docker-compose.atom-lab.yml` use the Compose Specification's
`!reset`/`!override` merge tags (to remove or replace inherited ports). These require a reasonably
recent `docker compose` CLI — tested with v5.3.1 here. If `make prod-up` or `make atom-lab-up`
fails with a YAML parse error mentioning `!reset` or `!override`, upgrade Docker Compose
(see [Merge Compose files](https://docs.docker.com/reference/compose-file/merge/)).

`docker-compose.yml` also defines a `migrate` service: a one-shot container (same image as
`platform-api`, `prod` target, entrypoint overridden to run `anytoolai-platform-migrate` and
exit) that applies Alembic migrations to head. `platform-api`/`platform-worker` declare
`depends_on: migrate: condition: service_completed_successfully`, so both wait for it to finish
before starting — and neither one runs migrations itself. See "Migrations and scaling" below.

Dev PostgreSQL is published only on `127.0.0.1`, using `ANYTOOLAI_POSTGRES_PORT`
(default 5432 for direct Compose; discover worktree ports with `dev-status`). The standalone
agent stack uses `127.0.0.1:55432`. API/worker use `postgres:5432` inside Compose;
production publishes no PostgreSQL host port.

Relying on loopback publication to prevent remote access requires **Docker Engine 28.0.0
or newer** with the default bridge networking configuration. On older Linux Engines, hosts
on the same L2 segment can reach localhost-published ports; see
[Docker's port-publishing warning](https://docs.docker.com/engine/network/port-publishing/).
Upgrade older Engines or enforce host firewall rules that block remote access to these
publications. `doctor` checks tool availability, not the daemon version; check it with
`docker version --format '{{.Server.Version}}'`. On shared or untrusted networks, verify
inaccessibility from a second host on the same L2 segment; a refused connection from the
Docker host itself is not a substitute for this check.

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
     `.env.prod` is gitignored (`.gitignore`'s `.env.*` rule) and picked up by `prod-up` via
     `--env-file`; `prod-fake-up` reads port overrides but replaces credentials and product selection
     with disposable fake-smoke values before Compose. Dev commands never read it. `prod-status` and
     `prod-down` use safe render-only values so they still work if `.env.prod` is missing or
     damaged. Best for a persistent local/server setup where re-exporting every shell session
     is annoying.

Public deployments must set `ANYTOOLAI_PRIVACY_POLICY_URL` to the approved absolute HTTP(S)
privacy-policy URL. `prod-up` rejects missing or invalid URLs before generating a deployment
profile or calling Docker, using Node.js's browser-compatible URL parser. The operator must confirm
the policy page is current and accessible; the preflight does not fetch or approve its contents.
Compose passes it as `NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL` at build time;
changing it requires rebuilding web-mirror. Every product form displays a data-processing notice
above submit. Empty or invalid URLs hide only the policy link; no policy URL is supplied by default.
Development, fake production smoke and maintenance commands keep the URL optional.

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
the operator environment or gitignored `.env.atom-lab`; never add them to `platform-worker`.

For a closed local check, set the code only in the shell that starts Compose:

```bash
export ANYTOOLAI_ATOM_LAB_ACCESS_CODE='replace-with-a-local-lab-code'
python3 scripts/agent/runner.py dev-up
```

Open the worktree-specific API URL reported by `dev-up` with `/atom-lab` appended. Enter the code in
the page; the page keeps it only in tab memory and sends it as a header. Do not place it in a URL,
committed `.env`, logs, screenshots, or browser storage. Use the HTTPS ingress profiles below.
Distribute the code separately and use the [rotation procedure](#shared-data-and-access-code-rotation)
for a Compose deployment.

### Internal Atom Lab Compose deployment

`atom-lab-*` is the reviewed deployment package for the private Lab. It composes the existing
`postgres`, one-shot `migrate`, `platform-api`, and `platform-worker` services from
`docker-compose.yml` with `docker-compose.atom-lab.yml`; it adds no service, database technology,
SSO layer, or public frontend. The API image already packages `/atom-lab` HTML/CSS/JavaScript.
PostgreSQL and the API publish their host ports on loopback. External access passes through an
operator-owned HTTPS reverse proxy.

For a separately launched local API process or custom local stand only,
`ANYTOOLAI_ATOM_LAB_AUTH_DISABLED=true` opens the Lab without a code. The standard Compose
environment does not forward this flag, and `atom-lab-*` commands always require and verify
access-code protection; adding the flag to `.env.atom-lab` does not disable it. No-code routes
require Host `localhost`, `127.0.0.1`, or `[::1]` and reject any Origin that differs from the
request's scheme, host, or port. Origin-free local CLI requests remain supported. The HTML
shell rejects framing in both modes. Keep access-code protection enabled behind remote ingress.

Bootstrap the [managed Python environment](vps-release-runbook.md#before-the-maintenance-window),
create the gitignored secret file with owner-only permissions, and set unique PostgreSQL
credentials, a high-entropy Lab access code, a different server live token, the worker-only
OpenAI key, the exact approved HTTPS origin, and a measured worker memory limit.
If no egress proxy is required, keep `ANYTOOLAI_LLM_HTTPS_PROXY=` blank; do
not leave a sample proxy hostname. Configure a real worker proxy only when required. Do not reuse
the Lab code as the live token or `/demo` code. Do not put any credential in a URL, command
argument, ticket, Git, screenshot, proxy access log, or evidence file. Readiness prints only the
configured origin.

```bash
install -m 600 infra/compose/.env.atom-lab.example infra/compose/.env.atom-lab
```

Before starting Compose, prepare the ingress configuration. For the internal network profile, enforce
TLS and a network/VPN allowlist before proxying `/atom-lab`, `/atom-lab/*`, and `/v1/atom-lab/*` to
the loopback API port. Remove `Cookie` and `Authorization` request headers and deny these paths on
public virtual hosts. For the shared-code deployment on VPS 135, use the routes and environment below.

```bash
python3 scripts/agent/runner.py atom-lab-up
python3 scripts/agent/runner.py atom-lab-status
python3 scripts/agent/runner.py atom-lab-ready
```

`atom-lab-up` fails before Compose if a required value or HTTPS origin is missing. The dedicated
`migrate` container must exit successfully before API/worker startup. Readiness verifies health,
all packaged assets, fail-closed missing/wrong codes, the authenticated eleven-atom catalog, and a
running worker. To protect a working installation from failed in-place cleanup, `atom-lab-up`
refuses to replace a running fixed project. For a reviewed update, follow the quiesce, backup,
`atom-lab-down`, and `atom-lab-up` sequence below; the named PostgreSQL volume and history remain
preserved. It does not claim that ingress is private or that a paid provider call succeeded.

After verifying HTTPS and the approved ingress profile, run the paid smoke in an approved
cost and maintenance window:

```bash
python3 scripts/agent/runner.py atom-lab-smoke
```

This reuses the A01-A11 live canary and its cost ceiling. After the runs finish, it drains the
queue, restarts API and worker, and checks the exact saved run IDs through the protected API.
For a deployment with an existing recorded live smoke run, the operator can verify persistence
using that run and its saved preset after a controlled restart. Record the live provider
result, restart time, and successful readback of the same IDs. Record the deployed commit and
approved HTTPS address. Keep access credentials and prompt, input, and result bodies out of
the report. Post-restart readback is required to complete ANY-468.

#### Atom Lab on VPS 135

The operator approved `https://any-tool-ai.ru/tools/atom-lab` as a VPS 135 exception to the
standard VPN/network allowlist. The page and static assets are reachable from any network.
Caddy forwards the protected Lab API routes, and the Lab API checks the shared code. Anyone
with the code can read shared Lab data and submit paid runs within the configured limits.
Issue the code privately to invited testers, agree what test data they may enter, and follow
the rotation procedure if it is disclosed. The separate Lab API, worker, and database
contain the Lab's data and jobs.
[Access policy](../../docs/product-specs/mvp-scope-source-of-truth.md#internal-atom-lab-exception)

Use these values in the Lab's gitignored `.env.atom-lab` with the PostgreSQL, Lab access, live
token, and worker credentials described above.

```dotenv
ANYTOOLAI_VPS_135_NETWORKS=1
ANYTOOLAI_ATOM_LAB_INTERNAL_URL=https://any-tool-ai.ru
ANYTOOLAI_ATOM_LAB_API_PORT=18114
ANYTOOLAI_ATOM_LAB_POSTGRES_PORT=15432
ANYTOOLAI_LLM_HTTPS_PROXY=http://egress-lb:3128
ANYTOOLAI_ATOM_LAB_RUN_DAILY_LIMIT=400
ANYTOOLAI_ATOM_LAB_RUN_ACTIVE_LIMIT=8
```

The limits apply to the whole Lab. The daily counter uses UTC. Up to eight queued or running jobs
can be accepted, and one worker runs them sequentially. The VPS overlay gives Caddy access to the Lab
API on `payments-portal-prod_edge` and gives the worker access to the provider proxy on
`infra_prompttune`. The database and migrator use the Lab's default network.

In the existing Caddy site’s `route` block, replace the `@anytoolai_private` matcher and its
`respond` line with this block. Keep it ahead of the generic `/tools/*` and `/v1/*` handlers.
The HTML uses two root asset URLs, and its browser requests use the root Lab API prefix.

```caddyfile
@atom_lab_page path /tools/atom-lab /tools/atom-lab/
@atom_lab_routes path /tools/atom-lab /tools/atom-lab/ /atom-lab/atom_lab.css /atom-lab/atom_lab.mjs /v1/atom-lab/*
route @atom_lab_routes {
	rewrite @atom_lab_page /atom-lab
	reverse_proxy atom-lab-api:8000 {
		header_up -Cookie
		header_up -Authorization
	}
}

@anytoolai_private path /atom-lab /atom-lab/* /tools/atom-lab/* /v1/atom-lab /v1/demo /v1/demo/*
respond @anytoolai_private 404
```

Validate the Caddy config and check the external HTTPS route after starting the Lab. Verify both
assets load, the catalog returns `401` with a missing or wrong code, a valid code unlocks the Lab,
and the four product routes still load. Keep the previous Caddy config for Lab rollback.

#### Shared data and access-code rotation

History and preset versions are shared by everyone with the Lab code. They may contain team-entered
prompts, inputs, and outputs, have no per-user attribution, and have no automatic retention/deletion
policy. Limit the code to the named internal group and agree what data may be entered. Preset
versions and accepted run snapshots are immutable; do not edit them directly in PostgreSQL.

For every planned rotation, first close ingress and drain all already accepted work:

```bash
python scripts/agent/runner.py atom-lab-quiesce
```

Only after quiesce succeeds, replace `ANYTOOLAI_ATOM_LAB_ACCESS_CODE` in the secret store or
`.env.atom-lab`, then recreate the application containers and require readiness:

```bash
python scripts/agent/runner.py atom-lab-down
python scripts/agent/runner.py atom-lab-up
python scripts/agent/runner.py atom-lab-ready
```

Verify the old code receives `401 atom_lab_access_denied`, and only then reopen ingress. Rotation
does not re-encrypt or delete history/presets. For a suspected leak, remove ingress immediately,
but still quiesce and drain already accepted work before changing the code and restarting the
stack; do not turn a paid in-flight provider call into a forced-stop failure merely to rotate the
admission credential.

#### Catalog and limits troubleshooting

An empty catalog disables runs until the worker completes its first provider catalog refresh. A
failed later refresh retains the last-good catalog marked stale. Inspect protected
`/v1/atom-lab/models` metadata and worker logs by timestamp/error code; never print environment
values. Confirm worker-only OpenAI/proxy egress, matching account scope, refresh lease/TTL/cooldown,
and host time. Manual refresh is coalesced and may be cooldown-limited. Restarting API does not
refresh the catalog, and deleting catalog/history rows is not a repair procedure.

The default API-only admission bounds are 384 KiB request body, 256 KiB input, 64 KiB prompt, 100
accepted starts per UTC day, and one active run. They are backend limits, not a model context-window
promise. Change them only in `.env.atom-lab`, keep them off the worker, and rerun deployment plus
readiness after review.

#### Upgrading PostgreSQL 16 to 18

PostgreSQL 18 is the pinned version everywhere in `main`. It landed in two revisions, because
step 1 below needs `prod-quiesce` on the revision that is still running PostgreSQL 16:

1. **Tooling revision** (ANY-713, `d1b20331`). Dev, agent, and CI use PostgreSQL 18; the prod and
   Atom Lab overlays still pin `postgres:16` with their existing volumes, and the runner gains
   `prod-quiesce` and `prod-recovery-postgres-up`. Deploy it the normal way (`prod-up`,
   `atom-lab-up`); no data moves.
2. **Switch revision** (ANY-714, `64ce95f9`, and later). The prod and Atom Lab overlays use
   PostgreSQL 18. The 18 image moved `PGDATA` to `/var/lib/postgresql/18/docker`, so they mount
   their volume at `/var/lib/postgresql` under **new names** (`postgres18-data`,
   `atom-lab-postgres18-data`). The old PostgreSQL 16 volumes (`postgres-data`,
   `atom-lab-postgres-data`) are never mounted by it and stay intact for rollback. Deploy it only
   with the steps below; otherwise it starts an empty database.

A host still on a checkout older than the tooling revision must deploy it first. Confirm with
`python scripts/agent/runner.py --help`, which must list `prod-quiesce` (prod) and
`atom-lab-quiesce` (Atom Lab). Below, "PostgreSQL 16 revision" means the tooling revision and
"PostgreSQL 18 revision" means the switch revision or later.

- **Dev and agent stacks** have no volume: `dev-down` then `dev-up` gives a fresh PostgreSQL 18.
  If a local overlay keeps a PostgreSQL 16 volume, `pg_dump -Fc` it first or recreate it.
- **Atom Lab** (dump/restore; do not use `pg_upgrade`). Keep `ANYTOOLAI_POSTGRES_DB` in
  `.env.atom-lab` unchanged: the dump is restored into that same database, not into a recovery
  database.

  ```bash
  LAB="docker compose --project-name anytoolai-atom-lab --env-file infra/compose/.env.atom-lab \
    -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.atom-lab.yml"
  PSQL='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc'
  ```

  1. While still on the PostgreSQL 16 revision, close ingress, run `atom-lab-quiesce`, and take a
     verified custom-format dump as described under "Backup, recovery, and rollback". Record the
     source row counts and Alembic head (below).
  2. Run `atom-lab-down` (never `down --volumes`) and check out the PostgreSQL 18 revision.
  3. Start only PostgreSQL on the new, empty `atom-lab-postgres18-data` volume and restore into
     `$POSTGRES_DB`. Do not run `migrate` first:

     ```bash
     python scripts/agent/runner.py atom-lab-recovery-postgres-up
     $LAB exec -T postgres sh -c "$PSQL 'show server_version'"      # must be 18.x
     $LAB exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' \
       < /operator/backups/anytoolai-atom-lab-YYYYMMDDTHHMMSSZ.dump
     ```

     Verify the row counts and `alembic_version` match the recorded source values. On any mismatch
     stop here: `atom-lab-down` and roll back.
  4. Run `python scripts/agent/runner.py atom-lab-down` (no `--volumes`; the restored volume is
     kept). This is required: `atom-lab-up` refuses with `LAB006` while any container, including
     PostgreSQL alone, is running.
  5. Run `atom-lab-up` and `atom-lab-ready`, confirm the same counts, then reopen ingress.
- **Prod** (`anytoolai-prod`). Lifecycle steps are runner commands; they hold the production
  deployment lock, bound every wait, and fail closed. `prod-quiesce` and
  `prod-recovery-postgres-up` use the base + prod Compose files, because the live overlay needs
  deployment-profile variables that only `prod-up` generates and it does not change `postgres`.
  The only raw Compose calls are the `pg_dump`/`pg_restore` `exec` lines below, with the same
  project, env file, and base + prod files:

  ```bash
  PROD="docker compose --project-name anytoolai-prod --env-file infra/compose/.env.prod \
    -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml"
  PSQL='psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc'
  ```

  Never use `$PROD up` (or any non-runner `up`/`start`) for `platform-api`, `platform-worker`, or
  `web-mirror`: that skips `prod-up`'s deployment profile, activation, and fingerprint checks and
  the live/VPS overlays. Application services come back only through `prod-up` and `prod-ready`.
  One named operator holds exclusive maintenance ownership from step 1 through step 5, because
  the runner lock cannot cover the raw `pg_dump`/`pg_restore` lines.

  1. **Quiesce, on the PostgreSQL 16 revision.** Close ingress, then run
     `python scripts/agent/runner.py prod-quiesce`. It stops the API, waits up to
     `ANYTOOLAI_PROD_QUIESCE_TIMEOUT` seconds (default 600) for every job to leave
     `created`/`running`, then stops the worker; PostgreSQL keeps running. On a nonzero exit
     (`PROD008`: query error or timeout) keep ingress closed, take no dump, and inspect
     `$PROD logs platform-worker`. To abort the window, run `prod-up` and `prod-ready`, then
     reopen ingress.
  2. **Dump and verify.**

     ```bash
     umask 077
     $PROD exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
       > /operator/backups/anytoolai-prod-YYYYMMDDTHHMMSSZ.dump
     ```

     Record the checksum, commit, UTC time, Alembic head, and source row counts (below). Prove the
     dump restores into a separate empty database on this PostgreSQL 16 instance (`createdb`,
     `pg_restore --exit-on-error`, compare counts, then drop it); a file existing is not evidence.
  3. **Switch revision.** `python scripts/agent/runner.py prod-down` (keeps volumes), then check out
     the PostgreSQL 18 revision.
  4. **PostgreSQL-only boot and restore.** `prod-recovery-postgres-up` refuses if any application
     container exists, starts only `postgres`, and waits for its health check, so the fresh
     `initdb` on `anytoolai-prod_postgres18-data` has finished before the restore:

     ```bash
     python scripts/agent/runner.py prod-recovery-postgres-up
     $PROD exec -T postgres sh -c "$PSQL 'show server_version'"      # must be 18.x
     $PROD exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --exit-on-error' \
       < /operator/backups/anytoolai-prod-YYYYMMDDTHHMMSSZ.dump
     ```

     Verify the row counts and `alembic_version` match the recorded source values. On any
     mismatch, stop and follow the rollback below.
  5. Run `python scripts/agent/runner.py prod-up` (migrate is then a no-op) and `prod-ready`,
     confirm the same counts, then reopen ingress.

  Row counts to compare (source vs. restored): `platform.jobs`, `platform.action_runs`,
  `platform.provider_calls`, `platform.event_log`, plus `alembic_version`.
- **Rollback to PostgreSQL 16.** Keep ingress closed throughout. Data written on 18 after the
  cut-over is not carried back; dump it first if it must be kept.
  - Prod: `python scripts/agent/runner.py prod-down`, check out the PostgreSQL 16 revision, then
    `python scripts/agent/runner.py prod-up` and `prod-ready`. That revision mounts the untouched
    `anytoolai-prod_postgres-data` volume. Reopen ingress only after `prod-ready` succeeds.
  - Atom Lab: `python scripts/agent/runner.py atom-lab-down`, check out the PostgreSQL 16 revision,
    then `atom-lab-up` and `atom-lab-ready`, which mount the untouched
    `anytoolai-atom-lab_atom-lab-postgres-data` volume.
- Remove the old volume only after the 18 deployment is accepted and a fresh verified backup of
  it exists.

#### Backup, recovery, and rollback

If the target Atom Lab PostgreSQL database already exists, back it up before every migration or
application update. A genuinely fresh initial deployment creates a new empty database, so there is
nothing to dump before its first start; take the first verified backup after durable data appears.
For an existing deployment, first close the Atom Lab ingress, then quiesce the application:

```bash
python scripts/agent/runner.py atom-lab-quiesce
```

`atom-lab-quiesce` holds the per-user lifecycle lock shared across checkouts and stops the API
so no new run can be accepted, leaves the worker running until every job in this deployment
database (Atom Lab, `/demo`, or ordinary runtime) has left `created`/`running`, and only then stops the worker.
PostgreSQL remains running. If the command returns nonzero, keep ingress
closed, do not take a backup, and inspect `atom-lab-status` and worker logs. After resolving the
problem, either rerun quiesce or abort the maintenance window with the idempotent
`python scripts/agent/runner.py atom-lab-resume`; resume starts API/worker and requires full
readiness before returning success. The same resume command safely reopens a successfully quiesced
application when the planned update is cancelled. Reopen ingress only after resume succeeds. On
successful quiesce, stream the custom-format dump without exposing a password
(replace the destination with a protected operator path):

The lifecycle lock serializes each runner command, but it cannot cover the raw `pg_dump` and
`pg_restore` commands below. One named operator/process must therefore hold exclusive maintenance
ownership from before quiesce through the verified dump and `atom-lab-down` (or `atom-lab-resume`).
During recovery, retain that ownership from before `atom-lab-recovery-postgres-up` through
`pg_restore` and the following `atom-lab-down`. No other shell, automation, or operator may run an
`atom-lab-*` command or direct Compose mutation in those intervals.

```bash
umask 077
docker compose --project-name anytoolai-atom-lab \
  --env-file infra/compose/.env.atom-lab \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.atom-lab.yml \
  exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' \
  > /operator/backups/anytoolai-atom-lab-YYYYMMDDTHHMMSSZ.dump
```

Record the checksum, commit, Alembic head, and UTC time. Test by restoring into a separate empty
database; file existence is not restore evidence. Never use `down --volumes`, `docker volume rm`, a
destructive Alembic downgrade, or in-place `pg_restore --clean` as rollback. `atom-lab-down`
preserves the named PostgreSQL volume. After the verified dump, run `atom-lab-down`, check out the
reviewed update, run `atom-lab-up` and readiness, then reopen ingress only after verification.

For the **initial ANY-468 rollout**, do not check out the pre-ANY-468 revision while the Lab is
running: that revision has neither the Atom Lab overlay nor its lifecycle commands. Close ingress,
use the currently deployed ANY-468 checkout to quiesce and back up any durable data as described
above, then run `atom-lab-down`, retain the named volume and verified backup, and check out the
previous revision. This returns the host to its pre-Lab application state without depending on
tooling that does not exist in that revision. If the Lab must be attempted again, check out a
reviewed revision containing this deployment package and run the normal recovery or deployment
procedure from that checkout.

For a **subsequent compatible-schema application rollback**, keep the current deployment checkout
until quiesce and the verified backup are complete, then remove its containers while retaining the
named volume:

```bash
python scripts/agent/runner.py atom-lab-down
```

Only after `atom-lab-down` succeeds, check out the prior reviewed Atom Lab revision. Reuse the
volume only if that revision supports the current schema, then run its `atom-lab-up` followed by
`atom-lab-ready`. This rebuilds/recreates application containers from the target revision; neither
`atom-lab-resume` nor `docker compose start` performs an application rollback. Verify protected
history and preset versions before reopening ingress.

For an **incompatible-schema rollback from a running deployment**, stay on the current revision
that contains the recovery tooling. Close ingress, run `atom-lab-quiesce`, and create a fresh
owner-only safety backup of the current/new schema with the dump command above (do not follow its
normal update step). This safety backup
preserves the state being abandoned; it is not necessarily the pre-upgrade dump used to return to
the target schema. Record both files unambiguously. Then remove every container while retaining the
volume, still without checking out the prior revision:

```bash
python scripts/agent/runner.py atom-lab-quiesce
# Create and verify a new-schema safety backup using the procedure above.
python scripts/agent/runner.py atom-lab-down
```

If rollback follows a failed `atom-lab-up` whose failed-candidate cleanup already completed
`atom-lab-down`, skip that quiesce/safety-backup/down sequence and start here. Bootstrap only
PostgreSQL from the preserved volume and wait for its health check. The helper inspects containers
in every state and fails closed unless the project contains at most PostgreSQL; it never starts
`migrate`, API, or worker. Restore the last verified **pre-upgrade** dump that is compatible with
the target revision into a separate recovery database:

```bash
python scripts/agent/runner.py atom-lab-recovery-postgres-up
docker compose --project-name anytoolai-atom-lab \
  --env-file infra/compose/.env.atom-lab \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.atom-lab.yml \
  exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" atom_lab_recovery_YYYYMMDD'
docker compose --project-name anytoolai-atom-lab \
  --env-file infra/compose/.env.atom-lab \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.atom-lab.yml \
  exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d atom_lab_recovery_YYYYMMDD' \
  < /operator/backups/anytoolai-atom-lab-YYYYMMDDTHHMMSSZ.dump
```

After the restore succeeds, stop the entire fixed project while preserving its named volume:

```bash
python scripts/agent/runner.py atom-lab-down
```

Only then check out the prior reviewed revision, change `ANYTOOLAI_POSTGRES_DB` in `.env.atom-lab`
to the recovery database name, and run that revision's `atom-lab-up`, followed by
`atom-lab-ready`. Do not check out a revision that may lack recovery tooling until the restore and
`atom-lab-down` have completed. This explicit down/up boundary is required because
`atom-lab-up` rejects any running container in the fixed project with `LAB006`; leaving PostgreSQL
running would make the recovery procedure fail closed. Verify protected history and preset
versions before reopening ingress. Keep the old database/volume until recovery is accepted and a
new backup is verified. `atom-lab-down` removes containers/networks, not history.

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

Run `python scripts/agent/runner.py quick-check` once first to bootstrap the managed Python
environment used to build and verify live profiles. With a real `OPENAI_API_KEY` and working
`ANYTOOLAI_LLM_HTTPS_PROXY` supplied only through the shell or gitignored
`infra/compose/.env.live`, run:

```bash
python scripts/agent/runner.py dev-live-up --product proposal_ai
python scripts/agent/runner.py dev-web
```

The first command generates an unmetered live profile. API and worker verify their mounted
profile against the selected manifest before either process starts; readiness checks both again.
The second command starts the local web host with the active live product selection in a
separate terminal. `dev-live-up` rebuilds the API and worker images before recreating
containers; the worker image and live entrypoints are not bind-mounted, so a cached image
would skip the activation guards. A failed or interrupted `dev-live-up` stops its Compose
candidate. Run more than ten Proposal AI submissions, check successful live provider
rows in `platform.provider_calls` and Squid CONNECT records, and confirm there is no quota GET
or `429`. Repeat with `dev-live-up --product proposal_ai --quota-mode canonical` and verify
normal quota exhaustion. Stop with `dev-down`; a later ordinary `dev-up` uses the canonical
fake-backed product configuration and restores the full development web list. Do not treat a successful local web render as proof
of an OpenAI call without the ledger and Squid evidence.

## Prod

Install Docker Engine with the Compose plugin, Python 3.12, `uv`, Node.js, and npm on the VPS.
Prepare the reviewed checkout and bootstrap the managed Python environment using the
[VPS release runbook](vps-release-runbook.md#before-the-maintenance-window). The live profile
generator uses that environment. Use `python3` wherever the host exposes Python 3 under that name.

Copy `infra/compose/.env.example` to gitignored `infra/compose/.env.prod`. Fill the PostgreSQL
user/password/database, a real `OPENAI_API_KEY`, the Squid URL in
`ANYTOOLAI_LLM_HTTPS_PROXY`, `ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai`,
`ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai`, and an explicit
`ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT` chosen from available VPS RAM (the sample is `768M`, not a
measured minimum). Set `ANYTOOLAI_PRIVACY_POLICY_URL` to the approved policy page before `prod-up`.
Keep all three public access-code variables blank. The shell overrides the
file even with an empty value. An explicitly empty `ANYTOOLAI_UNMETERED_PRODUCT_IDS` selects the
canonical quota; omitting the variable is an error. Never commit or print the completed file.
On VPS `135.106.164.145`, also set `ANYTOOLAI_WEB_BASE_PATH=/tools` and
`ANYTOOLAI_VPS_135_NETWORKS=1`. The latter selects the exact external networks
`infra_prompttune` and `payments-portal-prod_edge`; those networks must already exist.
For the current four-product release on this VPS, use
`proposal_ai,client_update_writer,brief_decoder,acceptance_builder` for both
`ANYTOOLAI_ENABLED_PRODUCT_IDS` and `ANYTOOLAI_UNMETERED_PRODUCT_IDS`.
`prod-fake-up` explicitly clears an inherited web base path and remains on base + prod only.
Every public enabled product must also have a registered web page; the production web build
rejects unknown product IDs before startup. The backend-only `kernel_demo` remains available
for credential-free CI smoke.

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
then force-recreates base + prod + live Compose, waits for API and web HTTP, and checks the
same mounted profile fingerprint and policy references inside API and worker. It never falls
back to fake. A per-user deployment lock shared across checkouts covers profile generation
through readiness, activation, and failure cleanup; a concurrent `prod-up` exits with `PROD007`
before touching the production project or active profile. If Compose startup or readiness fails, or the
command is interrupted before `active-profile` is replaced, `prod-up` stops the candidate
project without deleting its PostgreSQL volume; investigate before restarting production.
Once that marker is in place, an interrupt leaves the stack up. The activation directory
and marker are non-secret and are published as `0755` and `0644` so the non-root API and worker users
can read them after a restrictive umask.

Each deployment uses a new immutable profile directory. A failed redeploy leaves the previous
container bind source intact for restarts; old profiles are removed only after readiness passes.
The candidate worker verifies its profile but waits for `active-profile` to name its generation
before polling the production queue. The candidate API mounts the same activation state and returns
`503 deployment_not_active` for every pre-activation request except OPTIONS and the read-only
GET/HEAD health and product runtime-config endpoints needed by deployment readiness. A failed
candidate therefore
cannot accept durable workflow mutations or terminalize queued jobs
under an allowlist that never became active.
`prod-ready` repeats the live readiness check, including a runtime-config request through the
web server's same-origin `/v1/*` route. `prod-fake-up` is reserved for the credential-free
`kernel_demo` smoke in CI and uses the separate `anytoolai-prod-fake` Compose project, so it
cannot reconcile or replace the live `anytoolai-prod` services. It checks API, web, and web-to-API
routing; failed startup/readiness, or an interrupt before readiness, tears the smoke project
down so it does not keep the production host ports, and `prod-fake-down` is the explicit
cleanup command. It never passes `.env.prod` or an OpenAI key to the smoke containers. `prod-smoke`
tests that smoke stack, not OpenAI.

On VPS `135.106.164.145`, the operator-owned payments Caddy terminates HTTPS and shares
`payments-portal-prod_edge` with `web-mirror`; select `docker-compose.vps-135.yml` as documented
above. Preserve the existing payments `/api/*` and catch-all routes, and add the AnytoolAI routes
in this exact order without stripping `/tools`:

```caddyfile
{$CADDY_DOMAIN} {
	route {
		@anytoolai_private path /atom-lab /atom-lab/* /tools/atom-lab /tools/atom-lab/* /v1/atom-lab /v1/atom-lab/* /v1/demo /v1/demo/*
		respond @anytoolai_private 404

		@anytoolai_tools path /tools /tools/*
		reverse_proxy @anytoolai_tools web-mirror:3000 {
			header_up -Cookie
			header_up -Authorization
		}

		@anytoolai_api path /v1/*
		reverse_proxy @anytoolai_api web-mirror:3000 {
			header_up -Cookie
			header_up -Authorization
		}

		reverse_proxy /api/* payments-portal-prod-api-1:8000
		reverse_proxy web:3000
	}
}
```

When deploying Atom Lab on this VPS, use the [Lab routes above](#atom-lab-on-vps-135) in place of
the private matcher and its response.

Use the [Caddy procedure in the VPS runbook](vps-release-runbook.md#reload-or-restore-caddy-on-vps-135)
to validate the candidate and check the mounted file before accepting traffic. The product API and
web host publish ports on loopback, and product PostgreSQL has no host port. Preserve the
applicable route denies and sensitive-header removal when using another ingress.

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

The worker runs as non-root `platform-worker`, so the mounted PEM must be readable by it. The
numeric UID/GID is allocated by the base image and is not pinned: query it before granting access,
for example `docker compose ... run --rm --no-deps --entrypoint id platform-worker -u` (and `-g`),
and repeat after rebuilding the image. A Squid CA certificate is public: publish it as `0644` (or
grant that UID read access via ACL), never `0777`. A root-owned `0600` PEM fails with `EACCES` on
provider TLS calls. After switching to this image, verify the custom CA under the non-root worker,
for example
`docker compose ... exec platform-worker python -c "open('/run/secrets/squid-ca.pem').close()"`.

Do not commit the CA or override containing an operator path. A normal CONNECT tunnel needs no
custom CA. For an override, use an operator-owned Compose invocation that includes base, prod,
live, then this file; preserve the same required environment and profile mount.

### Acceptance and quota switch

1. Open the public site and check the page and runtime-config for every enabled product. Run one
   known scenario per product. Pick a registered product outside the enabled set and confirm
   its page and direct runtime-config, quota, and scenario-start requests return safe `404`.
2. From outside the VPS, verify the API, web, and PostgreSQL ports are unreachable directly.
   Verify Demo routes return `404` and the three access credentials on the product API are blank.
   With Lab disabled, check that its routes are blocked. With Lab enabled, check the page,
   both assets, and catalog access with a missing, incorrect, and valid code as described in
   [Atom Lab on VPS 135](#atom-lab-on-vps-135). Check worker-only OpenAI key and proxy wiring
   without recording environment values.
3. Run `prod-ready` to check the generated profile fingerprint in API and worker. Confirm
   `platform.provider_calls` rows for the smoke runs use the live provider policy and that Squid
   logs the corresponding CONNECT requests. Verify the smoke runs did not consume guest quota
   for unmetered products. To verify a quota change, submit more than ten unmetered runs for
   the affected product and compare its guest counters before and after. Save redacted run IDs
   and timestamps as evidence.
4. Record peak worker memory with `docker stats --no-stream` during a cold catalog refresh and
   real run. Check `docker inspect` for `RestartCount=0` and `OOMKilled=false`; retain memory
   headroom when choosing the production limit.
5. To enable canonical anonymous quota, set `ANYTOOLAI_UNMETERED_PRODUCT_IDS=` in `.env.prod`
   (and remove any exported override), then rerun `prod-up`. Verify a guest with pre-window
   quota rows retains its count; a guest first seen unmetered begins at zero. The web image need
   not change for quota mode alone; runtime config supplies the quota summary.

On VPS `135.106.164.145`, roll back ingress before stopping the affected stack using the
[VPS release runbook](vps-release-runbook.md#reload-or-restore-caddy-on-vps-135). For a product
rollback, run `python scripts/agent/runner.py prod-down` from the candidate checkout and preserve
the PostgreSQL volume. Other deployments should roll back to their previously reviewed
image/Compose revision and rerun `prod-up` with its matching environment. Removing the
live overlay alone is **not** a live deployment; use `prod-fake-up` only for the explicit
credential-free smoke path.

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
  plain DB-polling loop with no `HEALTHCHECK`, see "Health checks" below), so `docker compose ps`
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

## Health checks

App healthchecks are image-level `HEALTHCHECK`s (Trivy DS-0026, ANY-726). Compose does not
redefine them: a `healthcheck:` block in any overlay silently replaces the image's check.

| Service | Check | Proves | Trivy DS-0026 |
|---|---|---|---|
| `platform-api` | `GET /health` from inside the container (`base` stage, so dev and prod) | uvicorn answers HTTP; **liveness only**, no database check | fixed |
| `migrate` | disabled in `docker-compose.yml` (one-shot, no HTTP) | — | n/a (same image) |
| `web-mirror` | `GET /v1/products/<first ANYTOOLAI_ENABLED_PRODUCT_IDS>/runtime-config` through Next | Next answers and its `/v1/*` rewrite reaches API for the right product; `unhealthy` while API is down | fixed |
| `platform-worker` | none | — | **accepted, still reported** |

`web-mirror` waits on `platform-api` via `depends_on: condition: service_healthy`.

`platform-worker` accepted risk: it has no HTTP surface or heartbeat, so a process-exists or
`SELECT 1` probe would report a wedged poll loop as healthy, and nothing acts on `unhealthy`
(`restart: unless-stopped` only restarts an exited process; no service waits on the worker's
health). Jobs on a lost worker are recovered by the advisory-lock lease and reconciliation
sweep, and `*-smoke` is the real liveness proof (see "Verifying end-to-end"). The finding stays
visible in the report-only Trivy run; there is no `.trivyignore`. Upgrade path: a heartbeat the
poll loop refreshes plus a `HEALTHCHECK` on its freshness.

## Migrations and scaling

For the first reserve/consume-on-success application cutover, follow the
[ANY-507 quiesce, backup and rollback procedure](execution-metering-cutover.md).
It requires a fully drained queue and compatible API/worker code, including when reservation
storage was already prepared. A schema upgrade alone does not authorize mixing old/new workers.

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

## Portal capability manifest receiver (ANY-711)

The API exposes `GET /internal/v1/capability-manifest?tenant_id=anytoolai&region=ru`.
It reads the complete immutable registry, including disabled products and metrics, without
storage or provider access. Ordinary configuration declares all six products and the two
approved test metrics disabled; this endpoint does not enable commercial admission.

`ANYTOOLAI_TENANT_ID` and `ANYTOOLAI_REGION` select the trusted API scope (defaults:
`anytoolai` and `ru`). Both must exist in the loaded registry or startup fails. Runtime routes
use these same settings. Worker execution retains the scope carried by each job. Changing the
baseline creates no migration, reset or relabelling of existing `default` data; operators must
resolve any required historical data preservation before deploying a scope change. Broader
regional isolation remains ANY-282.

Configure `ANYTOOLAI_PORTAL_SERVICE_TOKEN` only in the receiver API's operator environment or
secret store. The base Compose file passes it through only when supplied; it is absent from
worker and frontend environments. Unconfigured receivers return safe `503 manifest_unavailable`
while guest and public runtime-config routes retain their ordinary behavior. Explicit empty or
malformed values fail startup. Tokens accept 32–256 ASCII Bearer characters (letters, digits,
`._~+/-`, with optional trailing `=` padding). Use a cryptographically random secret of at least
32 random bytes; syntax validation alone does not establish entropy. Settings repr/JSON and
validation messages redact secrets.

Portal sends the secret in `Authorization: Bearer <secret>` over TLS with certificate
verification. The credential identifies the trusted Portal caller, authorizes only manifest
read and binds to the configured tenant/region. Missing, invalid or duplicate credentials return
`401` with `WWW-Authenticate: Bearer`; an authenticated wrong or ambiguous scope returns `403`.
Missing required query fields return the normal safe `422` envelope. Errors preserve request
correlation; internal responses have `Cache-Control: no-store`. All requests carrying `Origin`,
including browser preflight, are rejected, and internal routes bypass public CORS handling.
The deployment activation gate also protects the manifest; it is not a readiness exemption.

For rotation, use one bounded rollout window:

1. Generate a new independent secret; configure it as `ANYTOOLAI_PORTAL_SERVICE_TOKEN` and
   configure the old secret as `ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS`. Restart the API.
2. Switch the Portal's server-side `KERNEL_SERVICE_TOKEN`, then verify the new credential.
3. Remove `ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS` and restart the API before closing the
   rollout window. Verify the removed token receives `401` and the new token still succeeds.

At most two distinct receiver tokens are accepted. A previous token without a distinct current
token fails startup. The previous slot is an operator-controlled overlap, with no automatic
expiry; do not leave it configured after rotation. Use independent secrets for each direction,
environment and regional connection. Guest/user, demo, Atom Lab, live-canary and reverse-direction
credentials grant no manifest authority. Retain private-zone network controls and the existing
production loopback API binding. TLS and network deployment are operator-owned prerequisites;
local API tests do not establish a deployed TLS connection or production commercial approval.

`create_app(config_root=..., bundles=...)` forwards explicit bundle sequences unchanged to
`build_runtime`: they replace the default product bundles. Omission or `None` preserves the six
standard products. Temporary complete configurations can use this seam through the real
ConfigLoader without mutating global defaults. The Kernel-owned `manifest-conformance` command
now verifies this configuration over ephemeral loopback TCP using the unchanged Portal typed
client in a fresh isolated process. It requires no database, Docker or full Portal/LBX stack.

Prepare the peer from Portal root with `python3.12 scripts/repo.py sync-api` (existing lock,
root `.venv`, no migrations). From Kernel root:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

The automated command generates its own disposable secrets and cleans up its own resources.
Manual QA uses the same harness: `--mode serve-test` keeps only the real test-configured Kernel
available; `--mode probe --kernel-base-url http://127.0.0.1:<printed-port>` invokes the isolated
Portal client with the explicit peer arguments above. Both manual processes require the same
new disposable `ANY711_CONFORMANCE_TOKEN` in their environments, never in arguments/URLs/logs.
The [complete secret setup, exact commands and cleanup procedure](../../docs/contracts/kernel-capability-manifest/v1/README.md#manual-isolated-qa)
also explains the pre-import patches blocking both Portal dotenv paths.

Local automated HTTP, poisoned-dotenv isolation, 92 Portal client/source regressions and manual
serve/probe/interrupt cleanup passed on 2026-10-29. The producer base is
`7634eb09533846268a96ade004bca518c580b588` plus the Step 4 diff, consumer
`2bb07d778edc5ea56011b0034ba24b0702ede81f`. All six products and both approved test metrics
are checked against the actual loaded registry. Instrumented storage/provider calls remain zero.
These results prove local code/HTTP interoperability with TEST-ONLY vocabulary; deployed TLS,
private-zone controls, production commercial approval and financial/paid execution are unproven.
Full verification results remain in the
[canonical plan](../../docs/exec-plans/completed/ANY-711-implementation-plan.md).

## Deployment lock storage

Run every prod and Atom Lab lifecycle command on a host as the **same system deploy user**.
All checkouts share persistent locks in `<account-home>/.local/state/anytoolai/deployment-locks`
on POSIX, or `<system-profile>\AppData\Local\anytoolai\deployment-locks` on Windows.
POSIX uses the effective UID's account-database home; Windows queries the current token's system
profile. The account-derived path is independent of HOME, USERPROFILE, LOCALAPPDATA, TMPDIR and
checkout. The runner preserves the original path for inspection: symlinks/junctions anywhere in
the profile path (including a safe linked home) are unsupported and fail closed. Configure a
direct account-home path instead; resolving an alias first would hide who can replace it.
Different system users do not share these locks.

The runner checks the full directory chain to the filesystem root, including parents above the
profile that could rename it. POSIX ancestors must be owned by root or the deploy user and must
not be group/other writable. A root-owned sticky directory is allowed only when its next child
is deploy-owned; a foreign-owned sticky directory is unsafe. The final directory and files are
created as 0700/0600 and must remain private and deploy-owned. Correct unsafe permissions as the
deploy user; do not use chmod 777.

Windows validates owners and DACLs through the filesystem root and on existing lock files.
The deploy user, SYSTEM, Administrators and TrustedInstaller are trusted owners/writers.
Above the system profile, sibling creation alone is allowed; untrusted delete/rename or
permission-changing grants are rejected. Within the profile, untrusted write grants are rejected,
including inheritance grants. Lock files also reject untrusted ReadData grants: a read-only
descriptor can hold the byte lock. This is checked before locking for both existing and newly
created files, including inherited ACLs; ordinary ancestor read/list grants remain allowed.
OWNER RIGHTS is evaluated as the verified object owner, and
inherit-only CREATOR OWNER is allowed because it grants rights to the checked child owner. Intermediate junctions/reparse points are rejected. Windows PowerShell
uses only its own system modules, independent of inherited PowerShell 7 module paths, and runs
the fixed local helper via -File with process-only RemoteSigned policy. Machine policy is unchanged.
Inspection
failure blocks deployment; correct the ACLs or layout instead of bypassing the check.

During migration, stop all lifecycle commands from old checkouts before using the new runner:
old runners use `/tmp` locks and cannot coordinate with the new location. Windows checkouts
that previously followed a redirected LOCALAPPDATA must also be stopped before switching to
the canonical system-profile location. Once no old runner is
active, old `/tmp/anytoolai-prod.deployment.lock` and `/tmp/anytoolai-atom-lab.deployment.lock`
markers can be removed. Never delete the new persistent lock files during operation; process
exit (including a crash) releases the lock automatically.


## ANY-766 paid authority receiver (Step 6)

The historical Step 6 checkpoint introduced migration `0019` and snapshot V2;
it was verified only against disposable test databases. Those versions are not
the current installation target. The current pair requires Kernel `0021`,
Portal `20261111_0011`, delegation V2 and snapshot V3. Follow
[reviewed image installation](#reviewed-images-and-independent-updates-any-766-step-17)
and the Portal-owned paired compatibility/cutover procedure linked there. Apply
migrations only through the environment's authorized procedure.

Set the API's existing `ANYTOOLAI_PORTAL_BASE_URL` and independent
`ANYTOOLAI_PORTAL_ACCESS_SERVICE_TOKEN` to reach Portal identity/snapshot reads.
The Portal receiver must explicitly grant session exchange/introspection and
`access-snapshot:read`. Kernel accepts only snapshot V3; no V1/V2 wire conversion
or local extension of expiry exists. HTTPS verification stays enabled; existing
settings permit loopback HTTP only in dev/test.

To grant Portal invalidation permission, explicitly set
`ANYTOOLAI_PORTAL_ACCESS_INVALIDATION_ENABLED=true` in the API receiver environment.
It defaults false. Existing current/previous `ANYTOOLAI_PORTAL_SERVICE_TOKEN`
slots then bind to the same trusted scope and `access:invalidate` permission.
Manifest-only credentials do not acquire it from any request field. Keep the
existing token rotation procedure and no-browser/no-store internal boundary.

Inspect `platform.paid_access_coherence` read-only when diagnosing revision or
snapshot refusal. Never delete or lower a floor to repair access. Request-driven
refresh obtains a document at or above the durable floor; cache eviction does not
remove that floor, its semantic identity or immutable usage history. Failed
identity/snapshot dependencies return safe refusals without creating new work.

Portal Step 13 selects the invalidation destination and outgoing key from each
snapshot recipient's `BACKEND_CONSUMERS` entry; legacy Kernel manifest settings
do not select delivery. Enable the receiver permission before starting that sender.
Compose peer connectivity, browser launch and usage/exhaustion are implemented.
Steps 16/17 supply focused paired local acceptance and build/install preparation.
The full matrix, remote installation, staging/live acceptance and production
rollout belong to ANY-767. Local evidence does not establish a connected or
approved deployment.
