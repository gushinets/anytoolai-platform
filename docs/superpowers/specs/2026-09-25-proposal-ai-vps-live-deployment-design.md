# Proposal AI VPS Live Deployment Design

**Date:** 2026-09-25
**Status:** Proposed
**Scope:** Deploy Proposal AI as the first public product on the existing AnytoolAI platform, call OpenAI through an operator-owned Squid forward proxy, remove the Proposal AI guest quota in production, and leave a reusable path for later products and local live-provider runs.

## 1. Outcome

The repository will support two deliberately different operating modes without editing canonical product files by hand:

- deterministic development and CI continue to use the checked-in fake-provider configuration;
- a selected product can use a checked-in live-provider overlay in local development or production.

The first production deployment selects `proposal_ai`, uses the existing `default_text_generation_v1` provider policy and OpenAI model alias, applies no Proposal AI quota, routes worker HTTP traffic through Squid, and serves the product through the shared `web-mirror` host.

Later products reuse the same worker, proxy, web host, Compose overlay, and runner command. Each product adds only its explicit live action configuration and, if required, its own production quota override.

## 2. Constraints and invariants

- Product code and frontends never select an LLM provider or model.
- OpenAI calls continue through Provider Gateway and the existing LiteLLM adapter.
- Only `platform-worker` receives `OPENAI_API_KEY` and outbound proxy settings.
- Platform API and worker load the same effective product definitions.
- Tests and normal `dev-up` remain credential-free and deterministic.
- No database migration is introduced for the unmetered product.
- No implicit global rewrite from fake policies to live policies is introduced.
- No new provider abstraction, deployment framework, or generic configuration merge engine is introduced.
- Secrets and proxy credentials are never committed.

## 3. Configuration layers

The deployment separates three concerns which must remain independently selectable.

### 3.1 Live provider

Add a deployment-owned live `action_configs.yaml` for Proposal AI under:

`infra/deployment/products/proposal_ai/live/action_configs.yaml`

It contains the same Proposal AI action definition as the canonical product file, except that `provider_policy_ref` is `default_text_generation_v1` instead of `default_fake_provider_v1`.

The file is a complete loader input, not a partial YAML merge. Docker Compose mounts it read-only over the canonical `action_configs.yaml` path in both Platform API and worker containers. This preserves the repository rule that definitions are explicit and avoids adding hidden merge behavior to `ConfigLoader`.

The existing provider policy and LiteLLM router remain the source of truth for retries, model alias, and the concrete OpenAI model. A later product may reuse this policy or supply a different named policy when its model or retry requirements differ.

### 3.2 Production quota

Add full production replacements under:

- `infra/deployment/products/proposal_ai/unmetered/product.yaml`
- `infra/deployment/products/proposal_ai/unmetered/quotas.yaml`

The production `product.yaml` omits `quota_policy_ref`. The production `quotas.yaml` contains `quota_policies: []` so the loader does not see an unused local quota definition.

These files are mounted read-only into Platform API and worker in production only. Local live-provider mode changes the provider but retains the canonical development quota unless a future explicit unmetered local mode is requested.

Absence of `quota_policy_ref` is the platform's existing representation of an unmetered product. It avoids fake large limits, quota writes, quota exhaustion responses, and a database migration.

### 3.3 Outbound network

The worker receives:

```text
OPENAI_API_KEY
HTTPS_PROXY
AIOHTTP_TRUST_ENV=true
```

The operator-facing proxy variable is named `ANYTOOLAI_LLM_HTTPS_PROXY`; Compose maps it to `HTTPS_PROXY` only inside the worker. The API and web containers do not receive the OpenAI key or Squid credentials.

The proxy value uses the usual Squid URL form:

```text
http://[user:password@]proxy-host:3128
```

Squid must allow CONNECT traffic to `api.openai.com`. The current model-catalog refresh can also reach `raw.githubusercontent.com`; the Squid allowlist must permit that host while catalog refresh is enabled.

If Squid performs TLS interception, its CA certificate is mounted read-only and exposed through `SSL_CERT_FILE`. A normal CONNECT tunnel requires no custom CA.

Proxy environment variables route normal application traffic but do not enforce network isolation. If direct egress must be impossible, the VPS firewall permits the worker host to reach only the Squid address and required infrastructure endpoints.

Docker image pulls and image builds use Docker daemon/build proxy configuration, not the worker's runtime proxy environment. This remains an operator concern and is documented separately from application runtime configuration.

## 4. Reusable local live mode

Add a product-owned Compose overlay:

`infra/deployment/products/proposal_ai/docker-compose.live.yml`

It defines Proposal AI's live action configuration as a Compose `config` and mounts it into both Platform API and worker. The repository runner resolves the selected product to this checked-in overlay rather than accepting unchecked shell paths.

Extend `scripts/agent/runner.py` with:

```text
python scripts/agent/runner.py dev-live-up --product proposal_ai
```

The command:

1. validates the product id against the composed product bundle;
2. resolves `infra/deployment/products/<product>/live/action_configs.yaml` inside the repository;
3. fails before Compose if the live file or `OPENAI_API_KEY` is missing;
4. optionally loads the gitignored `infra/compose/.env.live` file;
5. starts the normal base and development Compose files plus the selected product's `docker-compose.live.yml`;
6. prints the existing per-worktree API endpoint;
7. reuses `dev-ready` for readiness.

The existing `dev-down` command stops the stack. No source YAML is modified, so the next normal `dev-up` returns to the fake provider automatically.

The local web host remains the existing native command:

```text
pnpm --filter @anytoolai/web-mirror dev
```

This intentionally avoids adding a second process supervisor to `runner.py`. A one-command backend-plus-frontend launcher can be added only if repeated local use proves that two terminals are a material problem.

For every later product, a live action config and its tiny product-owned Compose overlay become release-checklist items. The generic command then works without changes to runner or central Compose files.

## 5. Production Compose and web delivery

### 5.1 Compose inputs

`prod-up` continues to load the gitignored `infra/compose/.env.prod`. It reads `ANYTOOLAI_ENABLED_PRODUCT_IDS`, validates each id, and includes that product's checked-in live overlay plus its optional production overlay. Proposal AI's production overlay is:

`infra/deployment/products/proposal_ai/docker-compose.prod.yml`

It mounts the two unmetered files into both API and worker. The central production Compose file remains product-neutral. When another product is released, its own overlay is added and its id is appended to the allowlist; runner and central Compose code do not change.

Required production values are:

```text
ANYTOOLAI_POSTGRES_USER
ANYTOOLAI_POSTGRES_PASSWORD
ANYTOOLAI_POSTGRES_DB
OPENAI_API_KEY
ANYTOOLAI_LLM_HTTPS_PROXY
ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai
```

Proxy credentials should preferably be avoided by allowing the VPS egress IP in Squid. If credentials are required, their presence in container environment metadata is documented as an operator-visible secret-handling limitation.

### 5.2 Web container

Add `infra/docker/web-mirror.Dockerfile` and a production `web-mirror` service. The image builds the existing pnpm workspace and runs the existing Next.js application; no new frontend package or server is introduced.

At build time, `PLATFORM_API_BASE_URL` is set to `http://platform-api:8000`, matching the existing Next.js `/v1` rewrite. The browser therefore uses same-origin `/v1` requests while the Next server forwards them over the private Compose network.

The production web port binds to loopback by default. An operator-owned Nginx or Caddy instance terminates public HTTPS and forwards the product domain to that loopback port. Squid is outbound infrastructure and is not used as the inbound reverse proxy.

The API port also binds to loopback rather than all host interfaces. PostgreSQL remains unpublished.

### 5.3 Released product visibility and admission

The shared web host and backend bundle currently contain more than one product. Add one deployment allowlist, `ANYTOOLAI_ENABLED_PRODUCT_IDS`, configured in production as `proposal_ai`.

`apps/web-mirror/src/products/registry.ts` uses it so unreleased product pages return the existing not-found state. Platform API uses the same value to reject runtime-config, quota, and scenario-start requests for disabled products before they reach product services. This prevents direct API callers from running a composed but unreleased product, including one that still points at deterministic fake output.

The variable's absence preserves the current development and test behavior with every registered product available. Its values must resolve to known product ids at startup; an unknown id fails startup instead of silently hiding a typo. Adding the next public product is an allowlist change plus that product's live configuration, not a new web service.

The backend still composes the complete default bundle set, preserving the API/worker/validation invariant. The allowlist is an API admission concern, not a product-definition filter, and the worker remains capable of completing already-accepted jobs during a rolling configuration change.

## 6. Unmetered frontend behavior

The backend already represents an unmetered product with `quota_summary: null`. Update the shared product runtime in:

`apps/web-mirror/src/products/runtime/ProductRunPage.tsx`

When runtime configuration reports no quota policy, the page does not call the quota endpoint and does not render quota state. The same guard applies after a completed run and after “start another”. This is shared behavior, not a Proposal AI special case, so later unmetered products inherit it.

## 7. Failure behavior

- Missing `OPENAI_API_KEY`: `dev-live-up` and production preflight fail before starting a live stack.
- Missing or unknown product live config: the runner fails with the expected path and no Compose mutation.
- Invalid live/product/quota YAML: startup and `validate-configs` fail closed.
- Unreachable or rejecting Squid: Provider Gateway records failed physical attempts using its existing ledger and retry policy; no direct fallback is added.
- OpenAI validation failure: existing PydanticAI validation attempts remain authoritative.
- Web cannot reach API: container health/readiness fails and `prod-ready` reports the failing surface.
- Quota endpoint accidentally called for an unmetered product: frontend tests fail; runtime remains safe because quota absence does not deny execution.

## 8. Change map

### New files

- `infra/deployment/products/proposal_ai/live/action_configs.yaml`
- `infra/deployment/products/proposal_ai/unmetered/product.yaml`
- `infra/deployment/products/proposal_ai/unmetered/quotas.yaml`
- `infra/deployment/products/proposal_ai/docker-compose.live.yml`
- `infra/deployment/products/proposal_ai/docker-compose.prod.yml`
- `infra/docker/web-mirror.Dockerfile`

### Modified runtime and deployment files

- `infra/compose/docker-compose.yml` — worker proxy mapping shared by local and production live mode.
- `infra/compose/docker-compose.prod.yml` — product-neutral web service, loopback ports, restart/resource/health settings.
- `scripts/agent/runner.py` — validated `dev-live-up --product`, enabled-product overlay composition, production web readiness/status output, and required production preflight.
- `apps/platform-api/src/anytoolai_platform_api/settings.py` and product-scoped route dependencies — parse and validate the deployment product allowlist and reject disabled product admission.
- `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` — no quota request when runtime configuration is unmetered.
- `apps/web-mirror/src/products/registry.ts` — deployment product allowlist while preserving current defaults.

### Tests and documentation

- `tests/test_runner.py` — product-id/path validation, missing-key failure, local live overlay selection, multiple production overlay composition, and unchanged normal dev mode.
- Platform API route/settings tests — unknown allowlist entries fail startup and disabled products cannot load runtime config, read quota, or start scenarios.
- `apps/web-mirror/test/ProductRunPage.test.tsx` — unmetered initial and repeat-run behavior.
- `apps/web-mirror/test/registry.test.tsx` — production allowlist and default registry behavior.
- Proposal AI/config-loader tests — effective live policy and unmetered product configuration load successfully together.
- `infra/deployment/README.md` — VPS prerequisites, `.env.prod`, Squid destinations, TLS, reverse proxy, deploy, rollback, and smoke procedure.
- `docs/product-specs/add-product-recipe.md` — live action config as a release requirement for products that call a real provider.

## 9. Verification

### Repository checks

1. Run `python scripts/agent/runner.py doctor` before implementation.
2. Add failing focused tests before each behavior change.
3. Validate the canonical fake configuration and the assembled Proposal AI live/unmetered configuration.
4. Run `python scripts/agent/runner.py validate-configs`.
5. Run `python scripts/agent/runner.py validate-architecture`.
6. Run focused backend, runner, and web-mirror tests.
7. Run `python scripts/agent/runner.py quick-check`.
8. Run `python scripts/agent/runner.py frontend-check`.
9. Run `python scripts/agent/runner.py full-check`.
10. Render `docker compose config` for development live and production combinations and inspect config targets, ports, and environment ownership.
11. Keep the existing credential-free Proposal AI and production kernel smoke tests on fake-provider paths.

### Local live smoke

1. Put the OpenAI key and optional proxy URL in `.env.live` or the shell.
2. Run `dev-live-up --product proposal_ai`.
3. Start `web-mirror` with its existing pnpm command.
4. Submit one Proposal AI request.
5. Confirm the provider-call ledger records OpenAI and the configured model.
6. Stop with `dev-down`, start normal `dev-up`, and confirm Proposal AI is fake-backed again.

### VPS acceptance

1. Build and start the production stack from `.env.prod`.
2. Confirm PostgreSQL is not host-published and API/web bind only to loopback.
3. Confirm public HTTPS serves `/products/proposal_ai` through the inbound reverse proxy.
4. Confirm another registered but unreleased product route returns not found.
5. Submit a real Proposal AI request and confirm successful OpenAI/provider ledger entries.
6. Confirm the Squid access log contains the OpenAI CONNECT request.
7. Repeat Proposal AI runs beyond the old limit and confirm there is no quota decrement or `429`.
8. If direct-egress enforcement is required, verify firewall logs show no bypass path.

## 10. Rollback

Rollback uses the previous application image and Compose revision. Database rollback is unnecessary because this design introduces no schema change. Removing the live and unmetered config mounts restores the canonical fake-provider and limited-quota definitions on the next container recreation.

The OpenAI key and Squid access can be revoked independently. Provider failures remain visible in the existing provider-call ledger.

## 11. Explicit non-goals

- Deploying a repository-owned Nginx, Caddy, Squid, DNS, or TLS automation stack.
- Replacing LiteLLM or PydanticAI.
- Selecting provider/model from the frontend.
- Automatically translating every fake policy to one live policy.
- Preparing live manifests for products that are not being released yet.
- Adding billing, authentication, rate limiting, or abuse protection beyond the requested unmetered guest behavior.
- Optimizing the first web image beyond a correct production multi-stage build.

## 12. Success criteria

- Normal development and CI remain fake-backed and credential-free.
- `dev-live-up --product proposal_ai` runs Proposal AI locally against OpenAI without source edits.
- Production Proposal AI calls OpenAI only from the worker and through the configured Squid route.
- Proposal AI production runs are unmetered and do not call the quota endpoint from the web runtime.
- The public web deployment exposes Proposal AI while unreleased registered products stay hidden.
- A later product needs only an explicit live action config, optional quota override, web registration/enablement, and product tests; core provider, proxy, Compose, and runner infrastructure remain unchanged.
