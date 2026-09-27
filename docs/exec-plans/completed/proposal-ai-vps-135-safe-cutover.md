# ProposalAI VPS 135 Safe Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task. Keep this plan separate from the existing ProposalAI live-profile implementation plan; this plan covers integration with the occupied VPS and public cutover.

**Goal:** Serve ProposalAI at `https://any-tool-ai.ru/tools/products/proposal_ai` with real OpenAI calls through the existing HAProxy, while PromptTune, payments portal, and extensions backend remain available.

**Architecture:** Keep the existing payments-portal Caddy as the sole owner of ports 80/443 and keep the existing apex-domain `/tools` route so no DNS change is required. Run AnytoolAI as its own `anytoolai-prod` Compose project under `/opt/anytoolai-platform`; join only its web container to the payments-portal edge network and only its worker to the PromptTune network. Build `web-mirror` with Next.js `basePath=/tools`, strip payment-site cookies and authorization headers before proxying `/tools` or `/v1` to AnytoolAI, then add the ordered Caddy routes after the new stack and proxy path pass private checks.

**Tech stack:** Python 3.12, uv, Docker Compose, Next.js, Caddy, PostgreSQL, LiteLLM, HAProxy, Squid.

**Spec:** `docs/superpowers/specs/2026-09-25-proposal-ai-vps-live-deployment-design.md`; existing implementation plan: `docs/exec-plans/completed/proposal-ai-vps-live-deployment.md`.

## Status

- State: completed
- Execution was authorized by the user's deployment request; the later Caddy-only recreation was separately approved after the stale-bind rollback.
- Owner: mixed (repository changes by agent; secrets, VPS cutover, and acceptance by operator).
- Created: 2026-09-27.
- Last updated: 2026-09-28.
- Review date: 2026-10-04.
- Next action: none; monitor the internal demo and address deferred production hardening separately.
- Blocker: none.

## Confirmed target state and boundaries

- The chosen direct link is `https://any-tool-ai.ru/tools/products/proposal_ai`. `/tools` is an application prefix, not a locale; the existing language selector continues to choose UI language.
- This internal MVP deliberately reuses the apex domain and does not add a DNS record. ProposalAI and payments portal therefore remain in one browser origin for this demo; Caddy must not forward the origin's `Cookie` or `Authorization` headers to AnytoolAI, whose current web flow uses `localStorage` rather than cookies.
- `any-tool-ai.ru` already resolves to `135.106.164.145`. The payments-portal Caddy already terminates its HTTPS. No DNS change or second public reverse proxy is needed.
- Current Caddy serves payments portal on `any-tool-ai.ru`, PromptTune on `api.anytoolai.store`, and extensions backend on `ds.ru.anytoolai.store`. Keep those routes and all existing Compose projects intact.
- PromptTune's HAProxy is `egress-lb:3128` on external Docker network `infra_prompttune`. It health-checks two Squid upstreams; both were `UP` on 2026-09-27. Do not edit or restart HAProxy or Squid for this release.
- Existing Caddy is already on external Docker network `payments-portal-prod_edge`. Connect AnytoolAI `web-mirror` to that network; do not make payments portal depend on an AnytoolAI-owned network.
- Existing API/web host ports 8000/3000 are free and production Compose binds them only to `127.0.0.1`. PostgreSQL remains unpublished. Host has 8 CPUs, 15 GiB RAM, 139 GiB free disk, and no swap; measure actual build and worker use rather than assuming headroom is unlimited.
- The VPS has Python 3.12 and Docker Compose 2.40.3. Host `uv`, Node, and npm were absent. Install only the tools the deployment checks actually need, in an isolated tool location; do not upgrade or restart Docker or existing services.
- Both `/opt/PromptTune` and `/opt/payments-portal` have pre-existing uncommitted changes. Preserve them. The only existing live configuration to edit for cutover is `/opt/payments-portal/deploy/caddy/Caddyfile.prod`.

## Accepted internal-demo risks and deferred hardening

- Public unmetered ProposalAI access and its associated OpenAI spend risk are explicitly accepted for this internal MVP. Do not add authentication, rate limiting, or a new quota design in this cutover plan.
- Same-origin isolation from the payments portal is deferred. For this demo, the required mitigation is to strip `Cookie` and `Authorization` before both `/tools` and `/v1` requests reach AnytoolAI; a dedicated subdomain remains the production hardening path.
- Images are built on the VPS. Keep Compose build concurrency at one, observe host/container resources before and after the build, and do not edit Caddy if an existing service regresses.
- A full immutable-image pipeline, automated external browser suite, PostgreSQL backup/restore automation, long-term monitoring, and log-retention policy are deferred beyond this internal demo.
- HAProxy counter movement correlated with the controlled run's time and successful provider ledger row is sufficient evidence for this demo. Consult HAProxy/Squid access logs only when concurrent PromptTune traffic makes that evidence ambiguous.

## Global constraints

- No `docker compose down`, `docker system prune`, Docker daemon restart, host-wide firewall change, or broad package upgrade on the existing projects.
- Do not expose AnytoolAI API, web, PostgreSQL, HAProxy, or Squid directly to the public network. Caddy remains the public entry point.
- Keep `OPENAI_API_KEY` and proxy settings only in `platform-worker`; never print `.env.prod`, Docker environment values, prompts, or response bodies in deployment evidence.
- `ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai` and `ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai` remain the approved first-release profile. The canonical product YAML remains fake-backed in Git.
- Build on the VPS with `COMPOSE_PARALLEL_LIMIT=1`. A build is not permission to change or restart an existing Compose project.
- Record the deployed AnytoolAI commit SHA and require its checkout to be clean. No registry, tag, or image-digest pipeline is required for this demo.
- Do not add a public Caddy route until a private ProposalAI run succeeds and HAProxy counters show the corresponding proxy traffic.
- A failed new-stack build or start must leave all existing containers and public routes unchanged. A failed public cutover must be reversible by restoring the previous Caddyfile and hot-reloading Caddy.

## File map

| File | Responsibility |
|---|---|
| `apps/web-mirror/next.config.ts` | Production-only `/tools` base path; keep root `/v1/*` as an external API rewrite with `basePath: false`. |
| `infra/docker/web-mirror.Dockerfile` | Supply the same base-path value at build and runtime. |
| `infra/compose/docker-compose.prod.yml` | Pass optional `ANYTOOLAI_WEB_BASE_PATH` to the web build/runtime; leave loopback ports and isolated database intact. The VPS sets `/tools`, while fake CI stays unprefixed. |
| `infra/compose/docker-compose.vps-135.yml` (new) | Attach worker to external `infra_prompttune` and web to external `payments-portal-prod_edge`, retaining each service's default AnytoolAI network. No other services join these networks. |
| `scripts/agent/runner.py`, `tests/test_runner.py` | Select that overlay only for live `prod-up`/`prod-ready` when `ANYTOOLAI_VPS_135_NETWORKS=1`; probe `/tools` for live web readiness and keep `prod-fake-up`, dev, and CI unprefixed and independent of server networks. |
| `apps/web-mirror/test/nextConfig.test.ts` (new) | Check production base path and root `/v1` rewrite versus the unchanged development paths. |
| `infra/deployment/README.md` | Record VPS commands, network ownership, Caddy route, checks, and rollback. |
| `/opt/payments-portal/deploy/caddy/Caddyfile.prod` (VPS only) | Add ordered `/tools` and `/v1` routes and private-route denies under the existing `any-tool-ai.ru` site; remove upstream `Cookie` and `Authorization` headers for both AnytoolAI routes. Preserve the three current sites and `/api/*` payment route. |

## Review focus

1. A production `/tools/products/proposal_ai` page must load its JS, CSS, and fonts under `/tools/_next/*`; payments portal's `/_next/*` must still load from payments portal.
2. The browser's root `/v1/*` requests must reach Platform API through `web-mirror`, while existing payment `/api/*` still reaches payments API. The same-origin web healthcheck must still pass.
3. The optional VPS overlay and `/tools` base path must never be selected by `prod-fake-up` or normal dev checks, where the two external networks do not exist; their existing root-page readiness remains valid.
4. Recreating AnytoolAI web/worker must retain their external network attachments through Compose, without any change to existing projects.
5. Caddy must deny `/tools/atom-lab`, `/tools/atom-lab/*`, `/v1/atom-lab`, `/v1/atom-lab/*`, `/v1/demo`, and `/v1/demo/*` before forwarding; forwarded AnytoolAI requests must contain neither the browser's `Cookie` nor `Authorization` header, and other established routes must return their pre-cutover status.

## Tasks

### Task 1: Make the web build safe under `/tools`

- [x] Add a failing focused config test: production build settings yield `basePath: "/tools"`, `/v1/:path*` remains reachable without that prefix, and dev build settings keep no base path.
- [x] In `next.config.ts`, read one build-time `ANYTOOLAI_WEB_BASE_PATH` value and set `basePath` only when present. Give the existing external `/v1/:path*` rewrite `basePath: false`.
- [x] Pass optional `ANYTOOLAI_WEB_BASE_PATH` into the production image build and runtime from the Dockerfile and production Compose file. Set it to `/tools` only in this VPS's `.env.prod`; leave dev and `prod-fake-up` unprefixed.
- [x] Run the focused frontend test, `python scripts/agent/runner.py frontend-check`, and a production web image build. Probe `/tools/products/proposal_ai`, a referenced `/tools/_next/*` asset, and `/v1/products/proposal_ai/runtime-config`; each must succeed, while `/products/proposal_ai` is not the production page.

### Task 2: Attach only the new containers to existing networks

- [x] Add failing runner tests showing `ANYTOOLAI_VPS_135_NETWORKS=1` appends the VPS overlay to live `prod-up` and its effective-profile check; live `prod-ready` probes `/tools` when `ANYTOOLAI_WEB_BASE_PATH=/tools`; and `prod-fake-up` clears the inherited base path and keeps its existing `/` readiness and Compose file list.
- [x] Add the minimal optional overlay selection and base-path-aware live web readiness to `runner.py`; reject VPS selector values other than unset or `1` before starting Compose. Explicitly clear `ANYTOOLAI_WEB_BASE_PATH` in `prod-fake-up`. `prod-status` and `prod-down` may keep their current project-scoped base/prod commands.
- [x] Add `docker-compose.vps-135.yml` with `platform-worker` on `default` + `infra_prompttune` and `web-mirror` on `default` + `payments-portal-prod_edge`. Confirm the effective Compose render preserves `platform-worker -> postgres/platform-api` and `web-mirror -> platform-api` connectivity.
- [x] Render base + prod + live + VPS Compose with disposable environment values, and render the existing production fake combination without the VPS overlay. Do not render real secrets to a log or terminal capture.
- [x] Run focused runner tests, `quick-check`, and `full-check`. Update the deployment runbook with the exact overlay selection and network names.

### Task 3: Capture a safety baseline on VPS before installing or starting anything

- [x] Record existing container names, image IDs, health, restart counts, memory use, Caddy routes, public HTTP status for payments portal, PromptTune API, and extensions backend, HAProxy server status/counters, free RAM/disk, and listening ports. Record statuses/IDs only, not secrets or user data.
- [x] Check for stale objects owned by the future Compose project with `docker ps -a --filter label=com.docker.compose.project=anytoolai-prod`, `docker volume ls --filter label=com.docker.compose.project=anytoolai-prod`, and `docker network ls --filter label=com.docker.compose.project=anytoolai-prod`. If `anytoolai-prod_postgres-data` exists, inspect it without printing stored data. Do not delete or reuse an unexpected object; stop and revise the plan.
- [x] Confirm the expected networks, ports, Caddy bind mount, and existing dirty Git state still match this plan. If they differ, revise the plan before acting.
- [x] Confirm payments portal does not currently use `/tools` or `/v1` for an active flow; keep its existing `/api/*` and `/_next/*` routing unchanged.
- [x] Save a dated copy of the active Caddyfile and a checksum. Do not reset or pull the dirty payments-portal or PromptTune checkouts.
- [x] Prepare only the needed standalone host tools and a clean reviewed AnytoolAI checkout at `/opt/anytoolai-platform`. Record `git rev-parse HEAD` and require `git status --short` to be empty; this SHA is the demo release identity. Run `python3 scripts/agent/runner.py doctor` and `quick-check`. Any tool installation must leave the existing container IDs and health unchanged.

### Task 4: Start and test AnytoolAI privately

- [x] Create gitignored `infra/compose/.env.prod` with mode `0600`: PostgreSQL credentials, OpenAI key, `ANYTOOLAI_LLM_HTTPS_PROXY=http://egress-lb:3128`, `ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai`, `ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai`, `ANYTOOLAI_WEB_BASE_PATH=/tools`, `ANYTOOLAI_VPS_135_NETWORKS=1`, `COMPOSE_PARALLEL_LIMIT=1`, and an explicit worker memory limit chosen with headroom. Keep demo, Atom Lab, and live-canary access codes blank. Do not print the file.
- [x] Confirm `docker compose config` resolves the two external networks and the production web build argument using disposable values. Confirm only `anytoolai-prod` will be mutated.
- [x] Immediately before `prod-up`, capture free RAM/disk and the existing containers' health/restart counts. Run `python3 scripts/agent/runner.py prod-up` with the configured single-operation Compose concurrency, then `prod-ready` and `prod-status`. The runner must report only `proposal_ai` enabled, both API and worker on the same live profile, a healthy web route, and no fake provider for the enabled product. Recheck the existing services and do not proceed to Caddy if their health/restart counts regress or host resource pressure remains unsafe.
- [x] Before changing Caddy, probe `http://127.0.0.1:3000/tools/products/proposal_ai` and its `/tools/_next/*` assets; submit one controlled ProposalAI run privately. Require a successful OpenAI provider-call ledger row and a time-correlated increase in the HAProxy `squid_primary` session counter (or `squid_backup` if the primary failed). If concurrent PromptTune traffic makes the delta ambiguous, consult existing HAProxy/Squid access logs rather than adding new tracing. Confirm worker reaches `egress-lb:3128`, web resolves from Caddy's shared network, and existing services still meet their baseline.
- [x] Record worker peak memory, restart count, and `OOMKilled=false`; increase only the new worker's limit and repeat the private run if needed. Do not open the public route on a failed proxy or resource check.

### Task 5: Cut over the new URL through the running Caddy

- [x] Prepare the smallest change to the existing `any-tool-ai.ru` Caddy site. In explicit route order: deny the private paths above; forward `/tools` and `/tools/*` without stripping the prefix to `web-mirror:3000`; forward `/v1/*` to `web-mirror:3000`; remove upstream `Cookie` and `Authorization` headers in both AnytoolAI reverse-proxy blocks; retain `/api/*` to payments API and all other paths to payments web. Leave `api.anytoolai.store` and `ds.ru.anytoolai.store` unchanged.
- [x] Validate the candidate Caddyfile. The first in-place attempt exposed a pre-existing stale read-only file bind and was rolled back. With explicit user approval on 2026-09-28, install the validated host file and use `docker compose ... up -d --no-deps --force-recreate caddy` to refresh only Caddy's bind; validate the newly mounted file and do not recreate any other payments service.
- [x] From outside the VPS, manually load `https://any-tool-ai.ru/tools/products/proposal_ai`; confirm the page hydrates with JS/CSS, switch language and reload, submit one real run, receive and copy a nonempty result, use the in-app link back to the tool list, and confirm browser API requests use root `/v1` rather than `/tools/v1`. Verify blocked internal paths and confirm the validated active Caddy config removes upstream `Cookie` and `Authorization` in both AnytoolAI proxy blocks without logging real header values. Recheck the three existing public services against the baseline immediately after reload and again after the real run; confirm the payments portal and its login surface still load normally.
- [x] Keep every pre-existing container except the explicitly approved Caddy-only recreation unchanged. If any old route or service regresses, restore the backed-up Caddyfile and recreate only Caddy before investigating the new stack.

### Task 6: Acceptance and rollback handoff

- [x] Verify API/web/PostgreSQL ports remain inaccessible externally; only worker has OpenAI/proxy environment variables by **name/presence**, not printed values. Verify disabled product pages and API admission return safe 404.
- [x] Compare all pre-existing container IDs, health, restart counts, and public HTTP statuses with the baseline. Confirm PromptTune HAProxy still has two available Squid servers and payments/extension routes remain healthy under the added traffic.
- [x] Save redacted evidence: reviewed commit SHA and clean-checkout result, target URL, Compose profile fingerprint, Caddyfile checksum/backup path, proxy counter delta, provider-call IDs/status, resource peaks, existing-service health/restart comparison, and exact rollback commands. Update this plan's progress log and the existing ProposalAI deployment plan's VPS acceptance result.
- [x] Rollback order if required: restore previous Caddyfile and recreate only Caddy first; verify old routes; then run `python3 scripts/agent/runner.py prod-down` in `/opt/anytoolai-platform` if the new stack must stop. This command must preserve the AnytoolAI PostgreSQL volume and must never target the `infra`, `payments-portal-prod`, or `extensions_backend` projects.

Exact rollback commands:

```bash
cd /opt/payments-portal
test "$(sha256sum deploy/caddy/Caddyfile.prod.backup-anytoolai-20260927T162324Z | cut -d ' ' -f 1)" = 74923e6cf74550d2f0f333347ebf219489a31ab310e429bc87c57e6d65d610d2
cat deploy/caddy/Caddyfile.prod.backup-anytoolai-20260927T162324Z > deploy/caddy/Caddyfile.prod
docker compose --project-name payments-portal-prod -f docker-compose.prod.yml config --quiet
docker compose --project-name payments-portal-prod -f docker-compose.prod.yml up -d --no-deps --force-recreate caddy
docker exec payments-portal-prod-caddy-1 caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
curl -fsS -o /dev/null https://any-tool-ai.ru/
test "$(curl -sS -o /dev/null -w '%{http_code}' https://api.anytoolai.store/)" = 404
curl -fsS -o /dev/null https://ds.ru.anytoolai.store/health

# Only if the new AnytoolAI stack must also stop; the PostgreSQL volume is preserved.
export PATH=/opt/anytoolai-tools/bin:$PATH
cd /opt/anytoolai-platform
python3 scripts/agent/runner.py prod-down
```

## Validation gates

- Repository: focused tests, `quick-check`, `frontend-check`, `full-check`, `validate-architecture`, `validate-docs`, and disposable Compose renders pass before copying source to the VPS.
- Private VPS: stale `anytoolai-prod` objects are absent or understood, the checkout is clean at the recorded SHA, `prod-ready` passes, a real ProposalAI result and provider ledger success correlate with an HAProxy counter increase, and pre-existing services retain their baseline before editing the live Caddy route.
- Public VPS: the direct link and manual browser/OpenAI run work; private routes are blocked; payment-site cookies and authorization are not forwarded to AnytoolAI; every pre-existing service matches its safety baseline.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-27 | Use `https://any-tool-ai.ru/tools/products/proposal_ai`. | The user accepted any direct path on the existing domain; `/tools` isolates the two Next.js asset trees. |
| 2026-09-27 | Keep payments-portal Caddy and attach only new AnytoolAI services to its edge and PromptTune egress networks. | Existing services must not depend on the new stack or be recreated for deployment. |
| 2026-09-27 | Prove a real proxy-backed OpenAI call before public routing. | HAProxy health alone does not prove LiteLLM sends ProposalAI traffic through it. |
| 2026-09-27 | Keep the apex-domain `/tools` route and make no DNS change for the internal demo. | The shortest path to a testable direct URL is preferred; same-origin production isolation is deferred. |
| 2026-09-27 | Strip `Cookie` and `Authorization` before `/tools` and `/v1` reach AnytoolAI. | The current ProposalAI flow needs neither header, and the demo should not expose payment-site credentials to the new stack. |
| 2026-09-27 | Accept public unmetered OpenAI usage for this internal MVP. | Authentication, abuse controls, and provider spend hardening are intentionally outside this cutover. |
| 2026-09-27 | Build on the VPS with Compose concurrency limited to one. | Avoid a registry/image pipeline for the demo while reducing peak build pressure on the occupied host. |
| 2026-09-27 | Use the clean checkout commit SHA as the demo release identity. | Full immutable-image release machinery is deferred, but the deployed source remains identifiable. |
| 2026-09-28 | Recreate only the Caddy service with `--no-deps --force-recreate` after explicit user approval. | The existing read-only file bind exposed an older file object, so in-place host edits could not produce a durable mounted configuration; the first attempt was fully rolled back before the exception was requested. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-27 | Read-only VPS inspection and deployment-route review complete; no server changes made. | Implement Tasks 1–2 after plan review, then execute gated VPS cutover. |
| 2026-09-27 | Plan review accepted the apex `/tools` route, public unmetered demo profile, on-VPS build, lightweight HAProxy evidence, SHA-only release identity, and manual browser smoke. Added header stripping, sequential build pressure control, and stale Compose-object preflight. | Implement Tasks 1–2, then execute the internal-demo VPS gates. |
| 2026-09-27 | Task 1 complete at `9073b11b`: optional `/tools` base path, root `/v1` rewrite, Docker/Compose propagation, and focused tests added. Production image built; `/tools/products/proposal_ai`, a `/tools/_next/*` asset, and root `/v1` returned 200 while the unprefixed product page returned 404. The full frontend gate ran in a clean local Docker context because a user-owned Windows Next process held the checkout's SWC binary. | Task 2: add the VPS network overlay and runner selection/readiness isolation. |
| 2026-09-27 | Task 2 complete at `a4f438c8`: live-only VPS overlay selection, `/tools` readiness, fake-mode isolation, exact external networks, and runbook guidance added. RED tests failed on the missing selector/base-path behavior, then focused tests passed. Disposable live/fake Compose renders preserved default connectivity and excluded VPS networks from fake mode. `quick-check` passed (`2038 passed, 7 skipped`); an exact clean Windows `full-check` passed the same backend baseline, lint, typecheck, frontend/browser tests, generated API drift, builds, and the 99-test Freelancer Suite. | Task 3: recapture the occupied-VPS baseline and stop before mutation on any drift. |
| 2026-09-27 | Task 3 complete. Pre-mutation audit found no stale `anytoolai-prod` container, volume, or network; expected external networks, free loopback ports, Caddy bind mount, and pre-existing dirty PromptTune/payments files matched the plan. Baseline HAProxy: both Squids UP, primary sessions total 592, backup 0. Existing container IDs/restarts remained unchanged after installing checksum-verified standalone uv 0.12.7 and Node/npm 24.18.0/11.16.0. Caddy backup: `/opt/payments-portal/deploy/caddy/Caddyfile.prod.backup-anytoolai-20260927T162324Z`, SHA-256 `74923e6cf74550d2f0f333347ebf219489a31ab310e429bc87c57e6d65d610d2`. Clean VPS checkout is `b09583815240e44d413f2070ee5f4b01714095b2`; VPS `quick-check` passed (`2045 passed`) and managed-venv `doctor` passed. | Task 4: create the protected production environment and prove the new stack privately. |
| 2026-09-27 | Task 4 complete. Created the gitignored mode-0600 production environment, rendered the exact external networks and `/tools` build path, and started only Compose project `anytoolai-prod` with `COMPOSE_PARALLEL_LIMIT=1`. `prod-ready`/`prod-status` passed with only `proposal_ai`, matching live API/worker profile fingerprint `01b6f91f8cc0bb7e20d3eb2a6108c6d5f50f6d764fd80725ec63661aa9927683`, and no fake provider. Private page, asset, and runtime-config probes returned 200; the unprefixed product returned 404. One controlled run completed with provider call `provider_call_01790527765639517751_0000000006_b8adb91617874ba5b0d5106345b41860` (`succeeded`, OpenAI via LiteLLM, 851 tokens, 5100 ms), while HAProxy primary sessions rose 596 -> 597 at the matching time. Worker peak was 254.4 MiB of 1 GiB, restart 0, `OOMKilled=false`; 13 GiB RAM and 133 GiB disk remained free, and every pre-existing container ID/restart/public status matched baseline. | Task 5: validate and hot-reload the minimal Caddy route, then perform public browser acceptance. |
| 2026-09-27 | Task 5 stopped at the required unexpected-state gate. The validated candidate was written to the host Caddyfile without changing its host inode, but the running container's read-only file bind continued to expose an older file object, so reload from `/etc/caddy/Caddyfile` did not install `/tools`. That stale mounted view also lacked the existing extension site; the prescribed rollback therefore restored the host backup and then hot-reloaded the verified backup through a temporary in-container path. Baseline is restored: payments 307, PromptTune 404, extensions root 401/health 200, Caddy ID `025067036b34...`, restart 0, host checksum `74923e6c...`. | Await an explicit choice between a direct validated temporary-file hot reload (leaving the mount-view mismatch until a future recreation) and a separately authorized Caddy-only recreation that refreshes the bind mount. |
| 2026-09-28 | Task 5 complete after explicit approval for a Caddy-only recreation. A fresh baseline and private `prod-ready` passed. The candidate checksum `77e383b630bdb049effa743328ae04ee2e2e175e0cf282d2df34517a33698f4e` was validated, written to the host path, and mounted by new Caddy container `2d9fa957affa...` via `--no-deps --force-recreate caddy`; every other container ID/restart count stayed unchanged. Public page, Next asset, and root runtime-config returned 200; all six private Demo/Atom Lab paths returned 404; header stripping appears exactly twice for each sensitive header. Manual browser acceptance passed hydration, locale persistence, a nonempty real result, copy confirmation, and return to `/tools`. Payments root/login UI, PromptTune, and extensions remained at baseline. No authenticated payments account was available in the isolated acceptance browser, so credential submission was not repeated. | Task 6: record final isolation, provider/proxy, resource, and rollback evidence. |
| 2026-09-28 | Task 6 complete. VPS checkout is clean at deployed SHA `b09583815240e44d413f2070ee5f4b01714095b2`; profile fingerprint is `01b6f91f8cc0bb7e20d3eb2a6108c6d5f50f6d764fd80725ec63661aa9927683`. Host and mounted Caddy checksums match `77e383b...`; backup is `74923e6c...`. Only the worker contains `OPENAI_API_KEY`/`HTTPS_PROXY` names. Disabled page/runtime/start return 404, proposal quota rows remain zero, API/web listen only on loopback, PostgreSQL is unpublished, and direct external application probes on 3000/8000/5432 time out. The public provider call `provider_call_01790528701256151352_0000000022_65e546d798554be4a54455f22e4766c4` succeeded through OpenAI/LiteLLM; both Squids remain UP and the primary session counter is 600 (private correlated proof was 596 -> 597). Worker is 254.6 MiB of 1 GiB, restart 0, `OOMKilled=false`; 13 GiB RAM and 133 GiB disk remain free. | Final diff review and independent code review. |
| 2026-09-28 | Fresh independent review found no Critical issues and confirmed the base-path implementation, VPS overlay isolation, runner fail-closed behavior, and Caddy evidence consistency. Its documentation findings were fixed: the canonical runbook now contains the actual ordered `/tools`/`/v1` Caddy routes, sensitive-header stripping, Caddy-only recreation, and durable rollback; the legacy plan distinguishes local canonical-quota proof from the selected unmetered VPS acceptance and has reconciled completion checkboxes; rollback verifies the backup checksum, mounted config, and PromptTune status. Fresh `quick-check` passed with 2038 tests and 7 skips; documentation and architecture validations passed. | Complete. |

## Open questions

- None. The measured worker peak was 254.6 MiB under the selected 1 GiB limit.

## Follow-up debt

- Runtime `HTTPS_PROXY` proves configured routing only when matched with HAProxy traffic evidence. Preventing all possible direct worker egress would require a container-specific network policy; avoid a host-wide firewall change that could interrupt the existing projects.
- Before a production launch, move the tools host to its own origin or complete a full same-origin cookie/CSRF/service-worker review, add abuse and spend controls, define immutable image delivery and application rollback, automate browser acceptance, and establish PostgreSQL backup, monitoring, and log-retention policy.
