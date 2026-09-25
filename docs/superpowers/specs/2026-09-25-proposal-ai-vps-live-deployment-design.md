# Proposal AI VPS Live Deployment Design

**Date:** 2026-09-25
**Status:** Approved for implementation after external review
**Scope:** Deploy Proposal AI as the first public product on the existing AnytoolAI platform, call OpenAI through an operator-owned Squid forward proxy, launch initially without a guest quota, retain a configuration switch for later anonymous quotas, and provide a reusable local/live path for subsequent Freelancer Suite products.

## 1. Outcome

The repository supports two modes without hand-editing canonical product files:

- normal development and CI load the checked-in fake-provider configuration;
- local live and production deployments generate a validated deployment profile from the current canonical product tree.

The first production profile enables only `proposal_ai`, changes its standard fake provider policy to the existing OpenAI-backed policy, makes its guest usage unmetered, routes worker HTTP traffic through Squid, and serves it through the shared `web-mirror` host.

The same mechanism can start any current Freelancer Suite product locally when its actions use `default_fake_provider_v1`. Later production releases reuse the generator, Compose overlay, worker, proxy, API, and web host.

## 2. Decisions and invariants

- Canonical product YAML remains the only committed product definition.
- Generated deployment profiles are gitignored runtime artifacts under `.agent/`.
- No committed full copies of `action_configs.yaml`, `product.yaml`, or `quotas.yaml` are maintained.
- Product code and frontends never select an LLM provider or model.
- OpenAI calls continue through Provider Gateway and the existing LiteLLM adapter.
- Only `platform-worker` receives `OPENAI_API_KEY` and outbound proxy settings.
- Platform API and worker mount and validate the same generated product tree.
- Normal `dev-up`, CI, and existing smoke tests remain credential-free and fake-backed.
- Quota selection is independent of provider selection.
- No database migration is required to enable or disable a quota.
- No generic YAML merge engine, provider abstraction, or deployment framework is introduced.
- Secrets and proxy credentials are never committed.

## 3. Generated deployment profile

### 3.1 Source and output

Extend `scripts/agent/validate_configs.py`, one of the three approved Freelancer Suite composition boundaries, with an explicit deployment-profile subcommand. The existing no-argument invocation used by `python scripts/agent/runner.py validate-configs` remains a read-only validation of the canonical bundle and never creates or changes `.agent/`. Only `dev-live-up` and `prod-up` invoke profile generation.

For each profile-generation run it:

1. resolves the canonical product roots through `FreelancerSuiteBundle`;
2. copies the complete current `products/` tree to `.agent/deployment-profiles/<compose-project>/freelancer-suite/products`;
3. transforms only the requested live products;
4. loads kernel config plus the generated product roots through the real `ConfigLoader`;
5. verifies the requested provider and quota modes;
6. writes a small machine-readable manifest containing the source directory, container target, live product ids, expected provider policy references, expected quota-policy reference or absence for each product, a source fingerprint for host-side staleness detection, and a profile fingerprint of the generated tree for container verification.

Both fingerprints use the same platform-independent SHA-256 input: files ordered by normalized relative path; for each file, a length-prefixed UTF-8 path using `/` separators followed by the length-prefixed exact file bytes. Absolute roots and filesystem metadata are excluded. The Windows host and Linux containers must therefore compute the same profile fingerprint for the same mounted tree.

Copying the tree at execution time prevents drift: prompt, schema, workflow, frontend, and product changes are present in the generated profile immediately. The profile is regenerated before every `dev-live-up` and `prod-up`.

### 3.2 Provider transform

For every selected live product, the generator replaces exact action-config references from:

```text
default_fake_provider_v1
```

to:

```text
default_text_generation_v1
```

It fails closed when:

- the product id is unknown;
- the product has no action config using the standard fake policy;
- a requested transform would leave a standard fake policy in that product;
- the generated registry does not resolve every changed action to the requested live policy.

The existing provider policy and LiteLLM router remain authoritative for retry behavior, model alias, and the concrete OpenAI model. This deliberately covers the current product family. If a future product needs different live policies per action, add a small explicit action-to-policy mapping then; do not guess that requirement now.

### 3.3 Quota modes

Each live product independently uses one of two quota modes:

- `canonical`: copy `product.yaml` and `quotas.yaml` unchanged, preserving the product's checked-in anonymous quota;
- `unmetered`: remove `quota_policy_ref` from the generated `product.yaml` and write `quota_policies: []` to the generated `quotas.yaml`.

The initial Proposal AI production profile uses `unmetered`.

Production selection uses:

```text
ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai
ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai
```

`ANYTOOLAI_UNMETERED_PRODUCT_IDS` must be a subset of enabled product ids. To restore Proposal AI's anonymous quota later, remove `proposal_ai` from that variable and redeploy. The generator then uses its canonical quota policy without code changes or a database migration.

New quota limits, periods, or dimensions remain product definitions and are changed in the canonical product YAML with normal tests and review. Deployment configuration only chooses whether that defined anonymous quota is active; it does not encode business policy in environment variables.

Quota usage behaves differently for guests with and without an existing usage row:

- unmetered scenario starts create no quota usage row; a guest first seen during an unmetered window starts from zero when canonical quota is later enabled;
- a usage row created before an unmetered window remains durable and resumes from its prior `used_count` when canonical quota returns;
- `ensure_usage` synchronizes an existing row's `limit_count` from the current canonical policy.

Preserve `proposal_ai.guest_quota_v1` when changing the canonical limit. Changing `quota_policy_id` intentionally selects a different usage key and gives every guest a fresh allowance. Changing quota dimension also selects different usage keys. The current kernel supports only `period: lifetime`; if additional periods are implemented later, changing period also changes `period_key` and therefore starts a new usage window.

`canonical` means “use whatever quota the product defines”, not “force a quota”. Proposal AI currently defines 10 lifetime product-level scenario runs. Client Update Writer currently defines no quota, so its canonical mode remains unmetered until a quota policy and `quota_policy_ref` are added to its canonical YAML.

Unset and empty unmetered-product configuration are distinct. In production, a missing `ANYTOOLAI_UNMETERED_PRODUCT_IDS` is a preflight error. An explicitly empty value means every enabled product uses canonical quota mode.

Local live mode defaults to `unmetered` so a persisted guest identity cannot exhaust a lifetime test quota. An explicit `--quota-mode canonical` option allows a real-provider quota test when needed.

### 3.4 Compose mount

Add one shared `infra/compose/docker-compose.live.yml` overlay. It read-only bind-mounts the generated Freelancer Suite `products/` directory over the editable package's container path in both Platform API and worker:

```text
/app/packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products
```

The source path comes from the validated profile manifest. The target is fixed because both current Docker images install the local Freelancer Suite dependency as editable from the repository copied to `/app`.

Mounting the generated directory once supports several enabled products without per-product Compose files or a dynamic YAML list.

## 4. Reusable local live mode

Extend `scripts/agent/runner.py` with:

```text
python scripts/agent/runner.py dev-live-up --product proposal_ai
python scripts/agent/runner.py dev-live-up --product proposal_ai --quota-mode canonical
```

`dev-live-up`:

1. resolves the per-worktree runtime identity;
2. optionally loads the gitignored `infra/compose/.env.live`;
3. requires `OPENAI_API_KEY`;
4. generates and validates the profile;
5. starts base Compose, the existing development overlay, and `docker-compose.live.yml`;
6. runs the in-container effective-config verification described below;
7. reuses `dev-ready` and prints endpoints plus the selected provider/quota modes.

The existing `dev-down` stops the stack. A subsequent normal `dev-up` omits the live overlay and returns to canonical fake behavior.

Local development does not require `ANYTOOLAI_ENABLED_PRODUCT_IDS`. When it is absent, Platform API and web-mirror expose every canonically registered product, preserving current `dev-up` behavior. This fallback is limited to local development: production preflight and the production Compose interpolation both require the allowlist.

Add a foreground command for the shared web host:

```text
python scripts/agent/runner.py dev-web
```

It derives the same worktree API URL, sets `PLATFORM_API_BASE_URL` before `next dev`, and invokes the existing `pnpm --filter @anytoolai/web-mirror dev`. This avoids the current incorrect fixed-port fallback without adding a process supervisor.

## 5. Production composition

### 5.1 Production input

`prod-up` continues to load the gitignored `infra/compose/.env.prod`. Runner resolves the required deployment values with the existing precedence (exported shell value over `.env.prod`), validates the enabled and unmetered product lists, generates the profile, and starts:

- `infra/compose/docker-compose.yml`;
- `infra/compose/docker-compose.prod.yml`;
- `infra/compose/docker-compose.live.yml`.

Required values are:

```text
ANYTOOLAI_POSTGRES_USER
ANYTOOLAI_POSTGRES_PASSWORD
ANYTOOLAI_POSTGRES_DB
OPENAI_API_KEY
ANYTOOLAI_LLM_HTTPS_PROXY
ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai
ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai
ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT
```

`ANYTOOLAI_UNMETERED_PRODUCT_IDS` is required but may be explicitly empty when every enabled product should use its canonical anonymous quota. Runner, not `${VAR:?...}` Compose interpolation, enforces that the variable is present: the latter rejects the valid empty value. An exported shell value takes precedence over `.env.prod` even when it is empty.

Before profile generation or Compose startup, `prod-up` prints the resolved enabled-product list and the resolved quota mode for each enabled product, for example `proposal_ai=unmetered` or `proposal_ai=canonical`. This output contains no secret values and makes an accidental empty shell override visible before deployment proceeds.

`infra/compose/docker-compose.prod.yml` requires `ANYTOOLAI_ENABLED_PRODUCT_IDS` with `${ANYTOOLAI_ENABLED_PRODUCT_IDS:?...}` wherever it supplies the API setting or web build argument. A production Compose render therefore fails even if runner preflight is bypassed. The web build also rejects a missing or empty public allowlist before `next build`.

Every enabled product must successfully transform to the live provider before Compose starts. Disabled products remain in the generated bundle tree with canonical configuration, but API admission and the web registry do not expose them.

### 5.2 Outbound Squid proxy

The live Compose overlay maps the operator-facing `ANYTOOLAI_LLM_HTTPS_PROXY` to the worker only:

```text
HTTPS_PROXY
AIOHTTP_TRUST_ENV=true
```

The API and web containers receive neither the OpenAI key nor proxy credentials.

Base Compose does not define `HTTPS_PROXY` or `AIOHTTP_TRUST_ENV`. Normal `dev-up` therefore cannot inherit an accidental LLM proxy from deployment configuration; proxy routing is present only when `docker-compose.live.yml` is selected. The existing base `OPENAI_API_KEY` wiring remains for the separate `live-canary` workflow.

The Squid URL uses:

```text
http://[user:password@]proxy-host:3128
```

Squid must permit CONNECT traffic to `api.openai.com`. Current best-effort model-catalog refresh also reaches `raw.githubusercontent.com`; failure to refresh the catalog does not stop Proposal AI execution.

If Squid performs TLS interception, its CA is mounted read-only and exposed through `SSL_CERT_FILE`. A normal CONNECT tunnel requires no custom CA.

Runtime proxy environment variables route application traffic but do not prevent direct egress. If bypass must be impossible, the VPS firewall restricts outbound worker traffic to the Squid address and required infrastructure endpoints.

Docker pulls and builds use Docker daemon/build proxy configuration, not the worker runtime variables. This remains an operator concern documented in the deployment runbook.

### 5.3 Released-product allowlist

Platform API reads `ANYTOOLAI_ENABLED_PRODUCT_IDS`. Unknown ids fail startup. Runtime-config, quota, and scenario-start routes reject disabled products before they reach product services.

The web pages are client components, so they cannot read that server-only variable at runtime. The web image build maps the same operator value to:

```text
NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
```

Next.js bakes it into the browser bundle. `apps/web-mirror/src/products/registry.ts` derives each registry entry's `enabled` field from the allowlist but preserves the complete registry array. `listRegisteredProducts()` continues to return every registered product so translation-completeness checks cover disabled products. `getRegisteredProduct()` keeps returning `null` for an entry whose `enabled` field is false, and the home page's existing `product.enabled` filter hides its card. The variable's absence preserves current development/test behavior with all registered products enabled.

A production browser smoke verifies both sides: Proposal AI loads, while another registered but disabled product returns the existing not-found state and cannot start through direct API calls.

### 5.4 Web container and inbound proxy

Add `infra/docker/web-mirror.Dockerfile` and a production `web-mirror` service. The image builds the existing pnpm workspace and runs the existing Next.js application.

The Docker build sets `PLATFORM_API_BASE_URL=http://platform-api:8000`, preserving the existing same-origin `/v1` rewrite over the private Compose network.

The Dockerfile declares and exports `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` before the `next build` layer and runs an explicit non-empty check before invoking `next build`. A missing production build argument therefore fails instead of baking an all-products fallback into the browser bundle. A changed product allowlist invalidates the build layer and creates a new browser bundle instead of reusing a stale one. Changing only quota mode does not rebuild web-mirror because the page derives metered versus unmetered behavior from API `quota_summary` at runtime.

Web and API host ports bind to loopback. PostgreSQL remains unpublished. An operator-owned Nginx or Caddy instance terminates public HTTPS and forwards the product domain to web-mirror. Squid is outbound infrastructure and is not used for inbound traffic.

Because Next currently forwards all `/v1`, the inbound reverse proxy explicitly denies:

- `/atom-lab` and its static assets;
- `/v1/atom-lab/*`;
- `/v1/demo/*`.

Production preflight also requires `ANYTOOLAI_DEMO_ACCESS_CODE`, `ANYTOOLAI_ATOM_LAB_ACCESS_CODE`, and `ANYTOOLAI_LIVE_CANARY_TOKEN` to be absent or blank for this public deployment. Existing application-level fail-closed checks remain defense in depth.

## 6. Unmetered frontend behavior

The backend already represents an unmetered product with `quota_summary: null`. Update `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` so it does not call the quota endpoint when runtime configuration contains no quota policy.

The same guard applies at initial load and after “start another”. Canonical-quota mode continues to fetch and render quota state normally, so switching Proposal AI back to anonymous quota requires no frontend change.

## 7. Effective-config verification

Profile validation happens twice, with different available inputs.

Before Compose, the generator compares the canonical source with the generated tree, loads the generated roots with the real `ConfigLoader`, asserts the requested provider/quota modes, and records the expected references and fingerprints in the host-side manifest.

After containers start, runner executes a read-only config check inside both Platform API and worker containers. It does not regenerate or mutate the profile and cannot compare against canonical YAML, which is not mounted there. The manifest remains on the host beside the generated tree; runner passes the expected profile fingerprint, provider policy references, and quota-policy reference or absence as check arguments. The check reads only the mounted product tree and asserts:

- the generated product tree is the root actually resolved by the editable bundle;
- every enabled action uses its host-validated expected live provider policy;
- every product has the host-validated expected quota-policy reference or has none, as specified;
- API and worker report the same profile fingerprint.

`prod-up` does not report ready if an enabled product still resolves any action to `default_fake_provider_v1`, the resolved bundle path is not the mounted generated tree, the profile fingerprints differ, or an expected provider/quota reference does not match. Canonical fake policies belonging only to disabled products are valid and do not fail readiness. Provider/model information remains internal and is not added to frontend-safe runtime-config APIs.

## 8. Resource limit

The existing worker limit of 512 MB has not been proven with a cold LiteLLM/OpenAI run and model-catalog refresh. Production therefore requires an explicit `ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT` rather than silently retaining an unverified value.

The target-VPS acceptance run records peak worker memory and verifies that the container was not restarted or marked `OOMKilled`. The operator chooses the initial value from available VPS RAM; after measurement it should retain practical headroom rather than match the observed peak exactly.

## 9. Failure behavior

- Missing OpenAI key, proxy, product allowlist, quota selection, or memory limit: production preflight fails before Compose mutation.
- Unknown product or unmetered id outside the enabled set: profile generation fails.
- Product without the standard fake policy: generic live transform fails and names the unsupported actions.
- Invalid generated YAML or cross-reference: `ConfigLoader` fails before containers start.
- Wrong or ineffective container mount: in-container effective-config verification fails readiness.
- Unreachable or rejecting Squid: Provider Gateway records failed physical attempts through its existing ledger and retries; no direct fallback is added.
- OpenAI validation failure: existing PydanticAI validation retries remain authoritative.
- Web cannot reach API: web health/readiness fails.
- Unmetered frontend accidentally requests quota: focused frontend tests fail; backend execution remains unmetered.

## 10. Change map

### New files

- `infra/compose/docker-compose.live.yml` — one read-only generated-product-tree mount for API and worker, plus proxy environment for worker only.
- `infra/docker/web-mirror.Dockerfile` — production Next.js image.

### Modified backend, runner, and deployment files

- `scripts/agent/validate_configs.py` — keep the default canonical validation read-only; add an explicit profile-generation/check entrypoint, profile-aware registry loading, fingerprints, and provider/quota assertions.
- `scripts/agent/runner.py` — `dev-live-up`, `dev-web`, production profile generation, `.env.live`, preflight, Compose file selection, effective-config checks, and web readiness/status output.
- `tests/test_runner.py` and config-validation tests — default validation remains canonical and does not write `.agent/`; explicit generation, strict transforms, quota modes, unset-versus-empty environment handling and resolved-mode output, cross-platform fingerprints, paths, disabled-product fake-policy acceptance, and identical read-only container-check commands.
- `infra/compose/docker-compose.yml` — retain existing OpenAI-key wiring for live canary; do not add proxy environment to normal development.
- `infra/compose/docker-compose.prod.yml` — product-neutral web service, loopback ports, required memory and product-allowlist interpolation, restart/resource/health configuration, and required web build arguments.
- `infra/compose/.env.example` — documented product allowlist, quota selection, proxy, and worker memory inputs.
- `apps/platform-api/src/anytoolai_platform_api/settings.py` and product-scoped route dependencies — parse/validate the server allowlist and reject disabled product admission.
- Platform API tests — unknown allowlist ids fail startup and disabled products cannot load runtime config, read quota, or start scenarios.

### Modified web files

- `apps/web-mirror/src/products/registry.ts` — derive each entry's `enabled` field from `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` while keeping `listRegisteredProducts()` complete.
- `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` — skip quota calls only when runtime config is unmetered.
- `apps/web-mirror/test/registry.test.tsx` — public build-time allowlist and default behavior.
- `apps/web-mirror/test/HomePage.test.tsx` — disabled products are absent from the home-page list.
- `apps/web-mirror/test/ProductRunPage.test.tsx` — both canonical-quota and unmetered flows.

### Documentation

- `infra/deployment/README.md` — VPS prerequisites, `.env.prod`, quota-mode switch, Squid, TLS, reverse-proxy denies, resource selection, deploy, smoke, and rollback.
- `docs/product-specs/add-product-recipe.md` — standard fake policy requirement for automatic live transformation and the explicit-mapping escape hatch for future products.

## 11. Verification

### Repository checks

1. Run `python scripts/agent/runner.py doctor` before implementation.
2. Add failing focused tests before behavior changes.
3. Run the explicit profile command to generate and validate Proposal AI profiles in both `canonical` and `unmetered` quota modes; verify identical fingerprints when the same fixture tree is addressed with Windows and POSIX path separators.
4. Generate live profiles for the other current standard-fake products to prove reuse without committed overlays.
5. Run `python scripts/agent/runner.py validate-configs` and verify that this canonical check creates no deployment profile or other `.agent/` output.
6. Run `python scripts/agent/runner.py validate-architecture`.
7. Run focused config, runner, API, and web tests.
8. Run `python scripts/agent/runner.py quick-check`.
9. Run `python scripts/agent/runner.py frontend-check`.
10. Run `python scripts/agent/runner.py full-check`.
11. Render `docker compose config` for local live and production combinations; verify production rendering fails without `ANYTOOLAI_ENABLED_PRODUCT_IDS` and the web image build fails without its public allowlist build argument. Separately verify runner rejects a missing `ANYTOOLAI_UNMETERED_PRODUCT_IDS` but accepts an explicitly empty value as canonical mode for every enabled product.
12. Keep existing credential-free Proposal AI and kernel smokes on canonical fake configuration.

### Local live smoke

1. Put the key and optional proxy in `.env.live` or the shell.
2. Run `dev-live-up --product proposal_ai`; confirm the effective profile is OpenAI-backed and unmetered.
3. Run `dev-web`; confirm it targets the derived worktree API port.
4. Submit more than ten Proposal AI requests without quota exhaustion.
5. Repeat with `--quota-mode canonical`; confirm the canonical anonymous quota applies.
6. Stop with `dev-down`, start normal `dev-up`, and confirm fake-backed behavior returns.

### VPS acceptance

1. Generate the production profile and inspect its manifest before starting containers.
2. Start the stack and pass effective-config verification in both API and worker.
3. Confirm PostgreSQL is unpublished and API/web bind only to loopback.
4. Confirm public HTTPS serves Proposal AI and hides/rejects disabled products.
5. Confirm public Demo and Atom Lab paths are denied and their credentials are blank.
6. Submit a real Proposal AI request and confirm successful OpenAI/provider ledger entries.
7. Confirm the Squid access log contains the OpenAI CONNECT request.
8. Repeat runs beyond the canonical limit and confirm the initial unmetered profile does not decrement quota or return `429`.
9. Deploy a canonical-quota profile in staging or a bounded acceptance window and confirm quota state and exhaustion behavior return without code changes.
10. Record worker peak memory during a cold catalog refresh plus real run; confirm no restart or OOM kill.
11. If direct-egress enforcement is required, confirm firewall logs show no bypass path.

## 12. Rollback

Rollback uses the previous application image and Compose revision. Removing `docker-compose.live.yml` restores canonical fake/provider quota definitions on the next container recreation. No schema rollback is required.

Switching only the quota mode is also reversible: add or remove a product id from `ANYTOOLAI_UNMETERED_PRODUCT_IDS`, regenerate the profile, and recreate API/worker containers. Rows created before the unmetered window remain durable and resume from their prior `used_count` when canonical quota returns. Guests first seen during the unmetered window have no usage row and therefore start from zero; unmetered starts are neither accumulated nor backfilled.

The OpenAI key and Squid access can be revoked independently. Provider failures remain visible in the existing provider-call ledger.

## 13. Explicit non-goals

- Deploying repository-owned Nginx, Caddy, Squid, DNS, or TLS automation.
- Replacing LiteLLM or PydanticAI.
- Selecting provider/model from the frontend.
- Encoding quota counts/periods/dimensions in environment variables.
- Supporting arbitrary per-action live-policy mappings before a product needs them.
- Adding billing, authentication, or abuse protection beyond the selected anonymous quota mode.
- Optimizing the first web image beyond a correct production multi-stage build.

## 14. Success criteria

- Normal development and CI remain fake-backed and credential-free.
- No committed deployment copy can drift from canonical product YAML.
- `dev-live-up --product <current-product>` runs any current standard-fake Freelancer Suite product against OpenAI without source edits.
- Local live defaults to unmetered and can explicitly test canonical anonymous quota.
- Production can switch Proposal AI between unmetered and its canonical anonymous quota through deployment configuration and container recreation.
- Production Proposal AI calls OpenAI only from the worker and through Squid.
- API and worker prove that they loaded the same generated profile before readiness succeeds.
- Public web/API admission exposes only enabled products and blocks Demo/Atom Lab surfaces.
- A later standard-fake product requires only its normal canonical config and tests plus an allowlist change; provider, proxy, Compose, runner, and web-host infrastructure remain unchanged.
