# Execution Plan: ANY-711 — Kernel Capability Manifest v1

## Status

- State: active
- Owner: mixed
- Created: 2026-10-29
- Last updated: 2026-10-29
- Review date: 2026-10-29
- Next action: implement the specified steps only after an explicit implementation request; application implementation has not started.
- Blocker: none at the architecture/planning level; dependency preparation and runtime verification remain future work.
- Development branch: `feature/ANY-711`, created by the owner from Kernel `main`.
- Review outcome: the accepted design is unchanged; all four accepted review clarifications are incorporated.
- Canonical plan: `docs/exec-plans/active/ANY-711-implementation-plan.md` in Kernel. Do not create a second independent Portal plan.

## 1. Goal & Final Expected Outcome

Implement [ANY-711](https://linear.app/paveldik/issue/ANY-711) within the accepted
[ANY-504](https://linear.app/paveldik/issue/ANY-504) boundaries.

A trusted RU Portal service calls the real Kernel application:

```http
GET /internal/v1/capability-manifest?tenant_id=anytoolai&region=ru
Authorization: Bearer <server-side service credential>
```

Kernel authenticates the caller, authorizes its configured scope and returns its complete
registered product and explicitly declared metric vocabulary. The existing Portal
`PlatformKernelClient` validates the response, references, exact scope and deterministic
semantic digest.

Two configurations must work:

- **Ordinary configuration:** returns all six registered products and both declared test
  metrics, including disabled entries. Commercial admission remains disabled unless
  explicitly configured otherwise.
- **Isolated test configuration:** enables ProposalAI and Brief Decoder with their approved
  test metrics. It uses complete temporary configuration copies loaded through the real
  ConfigLoader and application factory.

Configured operation returns `401` for missing/invalid credentials, `403` for authenticated
authorization failures and safe `5xx` when a complete valid manifest cannot be produced.
Invalid configuration may fail startup. No failure returns a partial successful manifest.

Concurrent calls, retries and restarts preserve the semantic version while configuration
semantics remain unchanged. Reads create no database writes, purchases, grants, scenarios,
jobs, provider operations or quota consumption.

Completion requires:

```text
real Kernel registry/config
→ real Kernel router and middleware over TCP HTTP
→ existing typed Portal client
```

The successful isolated scenario must verify all six products, both approved test metrics,
`anytoolai/ru`, references and digest. Fixture-only or replacement-handler tests cannot
satisfy this criterion.

The handoff must provide reproducible automated and manual procedures for starting this
real test-configured Kernel and invoking the existing Portal client.

This outcome does not establish production commercial approval, purchases, paid execution
or usage enforcement.

## 2. Current State & Reusable Implementation

### Observed baselines

Inspected on 2026-10-29:

- **Kernel:** `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`;
  `main` at `3c639c0a7de53c54cb6ce88e56a5813b73e76739`. Local and remote main agreed.
  The owner subsequently created `feature/ANY-711` at that commit; it is the current
  development branch. Do not recreate or rename it during step execution.
- **Portal:** `/home/wstanley/www/work_unirec/runtime-research/payments-portal`;
  clean `ANY-715` at `2bb07d778edc5ea56011b0034ba24b0702ede81f`.
- **Portal ANY-709:** `fc85a95e7011934801ac1a601e690726d8193f80` is included in
  inspected ANY-715. Manifest client and source composition are unchanged between these heads.
- **Portal main:** `ace7c277bbfda46e295fc9651d83e6a3a8fd1787`.
  Portal PRs [#150](https://github.com/gushinets/payments-portal/pull/150) and
  [#154](https://github.com/gushinets/payments-portal/pull/154) were unmerged at the observed
  baseline. Step 8 code is present despite stale planning-only wording in PR #154.
- Separate fixture PR [#151](https://github.com/gushinets/payments-portal/pull/151)
  remains open at the observation. The two-product fixture and matching pins were directly
  confirmed in ANY-715; their presence is not inferred from that PR.

Recheck relevant heads and review fixes before eventual execution. Use current Portal
ANY-715 while predecessors remain unmerged, or current main once it contains their required
result. Do not silently merge/rebase either repository. These are observed baselines,
not a requirement to freeze old commits.

### Kernel reuse and gaps

Reuse:

- ConfigLoader, immutable ConfigRegistry and product definitions.
- Core/SDK mirrored contract conventions.
- `build_runtime(config_root, database_url=..., bundles=...)`.
- Existing API dependencies, error envelopes and deployment activation.
- Config, architecture, bundle-parity, runtime and documentation checks.

The composed registry contains:

`kernel_demo`, `proposal_ai`, `client_update_writer`, `brief_decoder`,
`acceptance_builder`, `task_finder`.

Missing:

- Explicit product admission and metric declarations.
- Manifest projection, digest and endpoint.
- Scoped Bearer service authentication.
- Consistent RU scope configuration.
- Producer-owned contract artifacts and actual consumer conformance.

`create_app()` currently accepts `config_root` and `database_url`, but does not forward
a `bundles` parameter. Step 2 adds that narrow factory seam while preserving default composition.

Existing runtime region columns accept strings; no schema migration is planned.

### Portal reuse and import-time isolation

Reuse:

- `apps/api/app/integrations/kernel/client.py`
- `apps/api/app/composition/sources.py`
- `apps/api/app/core/settings.py`
- `apps/api/tests/support/settings.py`
- `apps/api/tests/support/kernel.py`
- Existing client/source tests and independent contract checker.

The client already implements strict v1 validation, scope/reference checks, independent
digest calculation, bounded HTTP behavior and certificate verification.

Portal settings have two dotenv paths:

1. `_load_settings_env_file()` invokes `load_dotenv()`.
2. Its returned path is passed to the import-time `Settings(...)` singleton, allowing
   Pydantic to read the file again.

Clearing inherited environment variables or constructing a later `Settings(_env_file=None)`
does not isolate that first import. Step 4 must block both paths before importing Portal
settings/client modules.

**No Portal application-code changes or second PR are required by the inspected compatibility
baseline.** Creating its ignored local `.venv` is permitted during eventual verification
preparation; Portal source files remain read-only.

`KERNEL_BASE_URL` and `KERNEL_SERVICE_TOKEN` already support configured sources.
`KERNEL_MOCK_ENABLED=false` selects `CONFIGURED_SOURCE`; provenance is not commercial approval.
Do not introduce a `GENUINE` enum or relabel retained simulated mapping evidence.

### Planning evidence

- Independent existing fixture/schema/digest checks: **PASS**.
- Timestamp/order stability and negative fixture checks: **PASS**.
- Positive fixture byte SHA-256:
  `25f39800090615eeba04cb27ab020332d0cf7cf7250fac6d2e5c38754c89b354`.
- Application and real-producer tests: **NOT_RUN**; the endpoint is not implemented.
- Kernel doctor previously failed because required Python packages were absent.
- Neither expected repository environment was prepared during planning.

These observations do not claim a new application, deployment, TLS or commercial PASS.

## 3. Architecture, Decisions & Dependencies

### Authority and ownership

Follow the current ANY-504/ANY-711 decisions and the Portal authority chain:

1. `docs/architecture/decisions/0005-external-billing-boundary.md`.
2. `docs/superpowers/specs/2026-09-15-external-billing-boundary-design.md`,
   especially Platform capability manifest and catalog freshness.
3. `docs/superpowers/specs/2026-09-15-portal-kernel-access-contract-design.md`,
   especially Scope key, Service authentication, Capability Manifest, and
   Versioning and contract fixtures.
4. `docs/superpowers/specs/2026-10-15-live-source-commercial-admission-design-amendment.md`
   and the accepted ANY-709 corrections.

Read each affected repository's actual instructions:

- Kernel root `AGENTS.md`, `ARCHITECTURE.md`, `docs/agent/coding-conventions.md`,
  `docs/agent/harness-engineering-map.md`, `docs/agent/codex-operating-model.md`,
  and `docs/integrations/payment-portal.md`.
- Kernel `docs/architecture/config-model.md`, `platform-boundaries.md`,
  `package-layering.md`, `quota-model.md`, and `docs/product-specs/add-product-recipe.md`.
- Portal root/API/docs subtree instructions, `ARCHITECTURE.md`,
  `docs/engineering/CODING_CONVENTIONS.md`, `AGENT_WORKFLOW.md`, `TESTING.md`,
  and `docs/integrations/platform-kernel.md`, where applicable.

Resolve stale integration-map snapshots through the current ticket and inspected consumer
code. Old statements describing blanket production-source prohibition do not override current
Portal settings.

Core remains product-neutral. It must not import SDK, product-platform packages, FastAPI or
Portal. Preserve identical default bundle composition across API, worker and config validation.

### Product configuration

Extend existing product definitions with:

```yaml
commercial_admission_enabled: false
usage_metrics:
  - metric_key: proposal_ai.test_generations
    unit: generation
    enabled: false
```

- `product.yaml` owns these explicit fields; no second catalog, database table or service.
- Every owned product YAML declares both fields; no metrics means `usage_metrics: []`.
- Metric ownership derives from the containing product.
- Core and SDK retain matching typed declarations under existing compatibility rules.
- Validate actual booleans, nonblank identities/units, declaration shape and global
  metric-key uniqueness, including disabled declarations.
- Freeze nested declarations with the registry.
- Do not derive commercial admission or metrics from guest quota, frontend flags,
  scenario counts or runtime product allowlists.

Initial vocabulary:

- `proposal_ai.test_generations` → `proposal_ai`, unit `generation`.
- `brief_decoder.test_analyses` → `brief_decoder`, unit `analysis`.
- The other four products have explicit empty metric lists.

Ordinary checked-in configuration keeps admission and these test metrics disabled.
The isolated test configuration enables the two approved examples only. Test declarations
do not approve production vocabulary, charging, failure or refund semantics.

Purchased quantities `100` and `300` remain Portal purchase-example data and never enter
this manifest.

### Application factory

Add:

```text
create_app(..., bundles: Sequence[ProductBundle] | None = None)
```

Forward `bundles` directly to `build_runtime()`.

- Omitted `bundles` and explicit `None` retain existing default composition.
- Explicit bundles retain existing `build_runtime()` replacement semantics.
- Do not append defaults to an explicit list.
- Do not change any default bundle constants.
- Tests must prove that explicit test composition does not alter later default
  application construction.

This is a composition seam, not a new public HTTP contract.

### Manifest v1

Expose exactly:

```text
schema_version: 1
tenant_id
region
manifest_version
generated_at
products[{product_id, enabled}]
usage_metrics[{metric_key, product_id, unit, enabled}]
```

Use API-owned response models without SDK metadata fields. Include every registered product
and declared metric, including disabled entries. No filtering or pagination.

Both product and selected metric must be enabled for new commercial admission.
Disablement does not revoke historical rights, reset usage or change runtime policy.

Hash only:

`schema_version`, `tenant_id`, `region`, `products`, `usage_metrics`.

Sort products by `product_id`, metrics by `metric_key`, and object keys recursively.
Use compact UTF-8 JSON with `ensure_ascii=False`. Exclude timestamp and digest fields.

Preserve the existing independent positive-example digest:

```text
sha256:a39bac9f210a6ac67e97e117f8481a5954dc3f36bdaab2fd54c7522b27d6ec29
```

The default-disabled configuration has different semantics and a different digest.

### Scope and authentication

- Add trusted `ANYTOOLAI_TENANT_ID` and `ANYTOOLAI_REGION`, defaulting to `anytoolai/ru`.
- Validate configured scope against the loaded registry during composition.
- Replace the temporary canonical `default` baseline with RU in bounded affected
  configuration, defaults, tests and documentation.
- Existing runtime routers and manifest use the same trusted settings.
- Workers preserve the scope carried by jobs; broader isolation remains ANY-282.
- No working-data reset, relabelling or customer migration. Unexpected data-preservation
  requirements are an explicit stop condition.

Receiver secrets:

- `ANYTOOLAI_PORTAL_SERVICE_TOKEN`
- Optional `ANYTOOLAI_PORTAL_SERVICE_TOKEN_PREVIOUS`

Require safe syntax, constant-time comparisons and bounded rotation overlap.
The previous token requires a distinct current token.
Bind credentials to the trusted Portal caller, configured scope and manifest-read permission.

User, guest, canary, Atom Lab and reverse-direction credentials do not authorize this
operation. Exclude internal routes from public CORS handling and reject browser-origin requests.

Missing receiver configuration must disable this boundary safely without breaking guest
routes. Malformed explicitly supplied configuration fails validation.
Preserve Kernel error envelopes, request correlation and activation behavior.
Configured authentication failures return `401` with a Bearer challenge; authenticated
authorization failures return `403`. No secret/raw settings leakage is allowed.

Use independent cryptographically random secrets per direction, environment and regional
connection. TLS with certificate verification and private-zone network controls remain
deployment requirements outside isolated local tests. No new TLS/OAuth/deployment platform
is introduced. Preserve the current production loopback binding.

Rotation: deploy new+previous receiver secrets, switch Portal, verify the new secret,
then remove the previous secret and prove rejection after restart.

### Eventual execution prerequisites

Saving or reviewing this plan does not authorize application implementation or environment
preparation now.

Before eventual Step 1 execution:

1. Recheck Kernel main and `feature/ANY-711`; use the owner-created branch.
   The required separate ANY-711 development branch already exists. Do not recreate it,
   switch branches or silently merge/rebase to reconcile a mismatch.
2. Use this single canonical plan in Kernel.
3. Prepare Kernel dependencies only when implementation is requested:

```bash
python3.12 scripts/agent/runner.py quick-check --bootstrap-only
.quick-check-venv/bin/python scripts/agent/runner.py doctor
```

Before Step 4 HTTP verification, from Portal root:

```bash
python3.12 scripts/repo.py sync-api
```

This uses the existing lock file and repository-root `.venv`. Do not regenerate locks,
create `apps/api/.venv`, run migrations or start a database/full Portal/LBX stack for this
verification.

Read-only restrictions apply to Portal sources and tracked artifacts; they do not prohibit
creation of its local dependency environment during the authorized future verification step.

## 4. Functional DoD & Acceptance Coverage

- **Complete ordinary registry, including disabled entries:** Steps 1–2 projection/API tests
  and Step 4 ordinary-config HTTP probe.
- **Enabled approved test vocabulary:** Step 4 complete temporary configuration and actual
  HTTP probe.
- **Six products, two exact metrics, owner/unit references and scope:** Steps 1–4 inventory
  and consumer assertions.
- **Strict v1, deterministic digest and generated schema correspondence:** Steps 1 and 3,
  then real consumer verification in Step 4.
- **Authentication, authorization, rotation and safe failures:** Steps 2 and 4.
- **Read-only retries/concurrency/restart:** Steps 1–2 and Step 4.
- **Default composition unchanged:** Step 2 factory tests and existing
  API/worker/validator parity tests.
- **No working `.env`, LBX credentials, worker or webhook influence:** Step 4 pre-import
  isolation and canary tests.
- **Reproducible manual QA and durable handoff:** Step 4 and section 7.

All Functional DoD criteria have a responsible step and verification.
Runtime verification stays NOT_RUN until implementation and execution actually occur.

## 5. Sequential Implementation Steps

- [ ] Step 1 — Declare and validate technical capabilities
- [ ] Step 2 — Serve an authenticated manifest in the trusted RU scope
- [ ] Step 3 — Publish and verify the producer contract
- [ ] Step 4 — Prove real HTTP interoperability with an isolated Portal client

### Step 1 — Declare and validate technical capabilities

**Goal**

Make the existing composed registry the complete typed authority for product admission
and technical metrics.

**Expected behavior**

Valid configuration produces one immutable capability vocabulary. Invalid or duplicate
declarations prevent registry construction. A pure projection produces complete manifest
semantics and a deterministic digest without storage or network access.

**Read before implementation**

- **Repository / Working directory:** Kernel,
  `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`.
- **Baseline:** `feature/ANY-711`, based on the observed/current reviewed main.
- **Prerequisites:** saved canonical plan and prepared Kernel dependencies.
- Read Core `products/models.py`, `config/loader.py`, `config/registry.py`;
  SDK `contracts/product.py`; API bootstrap; worker composition;
  `scripts/agent/validate_configs.py`.
- Reuse structured loader diagnostics, registry freezing, Core/SDK compatibility
  and bundle-parity tests.

Core paths above are under
`packages/backend/platform-core/src/anytoolai_platform_core/`; SDK paths are under
`packages/backend/platform-sdk/src/anytoolai_platform_sdk/`.

**Implementation**

- Add the declarations defined in section 3 to Core/SDK models and all six owned product YAMLs.
- Keep ordinary admission/test metrics disabled.
- Update relevant fixture bundles and constructors.
- Validate declaration shape, owner/unit identity and global metric-key uniqueness.
- Freeze nested declarations.
- Add a product-neutral complete projection/digest function.
- Preserve declarations through existing deployment-profile copying.
- Update config-model and add-product documentation.

**Invariants / Non-goals**

No second catalog, database tables, guest-quota-derived metrics, action charging
or usage accounting.

**Verification**

```bash
.quick-check-venv/bin/python -m pytest -q \
  packages/backend/platform-core/tests/unit/test_config_loader.py \
  packages/backend/platform-core/tests/test_contract_field_compatibility.py \
  packages/backend/platform-sdk/tests/test_contracts_importable.py \
  apps/platform-api/tests/test_bundle_composition.py \
  tests/architecture/test_bundle_composition_parity.py
```

Add focused tests for complete disabled output, invalid values, global duplicates,
immutability and semantic hashing. Run config/architecture guards and changed-file
Ruff formatting/checks.

**Expected completion**

After this step, Kernel can validate and project its complete vocabulary without HTTP,
database or provider dependencies.

**AI execution prompt**

```text
Implement Step 1 of the canonical ANY-711 plan.

Repository: /home/wstanley/www/work_unirec/runtime-research/anytoolai-platform.
Baseline: feature/ANY-711 from current reviewed main, with the canonical
plan saved and Kernel dependencies prepared.

Read Core product/config models, loader and registry; SDK product contracts;
API bootstrap, worker composition and config validator; existing loader,
Core/SDK compatibility and bundle-parity tests.

Add explicit commercial_admission_enabled and usage_metrics declarations.
Declare both approved test metrics disabled in ordinary configuration and
empty metric lists for the other products. Validate strict declaration
shapes, global uniqueness and owner/unit identity; freeze nested data.
Implement a pure complete projection and accepted semantic digest.
Preserve all default bundle, guest quota and runtime behavior.

Run the Step 1 focused tests, new negative/projection tests,
validate-configs, validate-architecture and changed-file Ruff checks.
Expect complete immutable vocabulary and deterministic hashing;
invalid declarations must fail registry construction.

Work only in the repository/directories and baseline specified by this step. Follow each affected repository's root and applicable subtree AGENTS.md files, ARCHITECTURE.md and its actual coding/workflow/testing instructions. In Kernel, include docs/agent/coding-conventions.md and the applicable harness documentation. In Portal, use the applicable docs/engineering conventions, workflow and testing documents where present. Do not assume Portal-specific documentation paths exist in Kernel. Respect architectural layers, typing, error handling, transaction ownership, dependency direction and established project structure.

Implement only the specified step of the single canonical ANY-711 plan stored in Kernel. Reuse existing components and preserve the accepted Portal contract, isolated-zone model, approved test vocabulary and functional outcome. Do not broaden the scope, start subsequent steps or implement paid access/usage accounting. Do not rewrite the existing Portal client without a demonstrated compatibility need.

Run appropriate formatters, linters and focused automated tests. Fix failures caused by your changes and rerun affected checks. Run additional relevant validation when necessary; report unexecuted or blocked checks accurately.

If a material contradiction appears, investigate the relevant surrounding context and available evidence, then propose a resolution. Stop and ask only when an important decision cannot be made safely.

Do not run mutating operations against real billing or other external production systems without explicit authorization. Use only authorized isolated local test resources; do not stop unrelated stacks, reset active development databases, expose secrets or deploy to a shared stand/production.

Do not stage, commit, push, switch branches, merge or rebase. Do not modify unrelated worktrees or publish PRs/ticket updates. Report a baseline mismatch; do not silently change Git history to resolve it.

Report the implemented behavior, changed files, verification results, remaining limitations and any required manual QA.
```

**Proposed commit**

`ANY-711 - Declare and validate Kernel capability vocabulary`

### Step 2 — Serve an authenticated manifest in the trusted RU scope

**Goal**

Expose the real private endpoint and the explicit application-factory composition seam.

**Expected behavior**

An authorized Portal request receives the complete real registry. Invalid credentials/scope
refuse safely. Existing runtime routes use RU and remain independent of manifest credential
configuration.

Default application construction retains the existing six-product composition.
Explicit test bundles can load temporary product roots without modifying defaults.

**Read before implementation**

- **Repository / Working directory:** Kernel, same directory as Step 1.
- **Baseline:** `feature/ANY-711` with completed Step 1.
- **Prerequisites:** validated declarations and pure projection.
- Read API `main.py`, `bootstrap.py`, `settings.py`, `dependencies.py`,
  `errors.py`, `schemas.py`, runtime-config router and activation handling under
  `apps/platform-api/src/anytoolai_platform_api/`.
- Read `configs/kernel/regions.yaml`, scope-dependent fixtures,
  `infra/compose/docker-compose.yml`, `docker-compose.prod.yml`
  and deployment documentation.

**Implementation**

- Add optional `bundles: Sequence[ProductBundle] | None = None` to `create_app()`
  and forward it unchanged to `build_runtime()`.
- Preserve omitted/None defaults and explicit-list replacement semantics.
- Add trusted scope settings and startup validation; align the bounded runtime baseline with RU.
- Add named manifest response models, router and Bearer declaration.
- Use the complete registry projection and an aware UTC response timestamp.
- Implement credential rotation, caller/scope/operation authorization and safe failures.
- Exclude internal routes from public CORS; reject browser-origin requests.
- Preserve activation gating.
- Pass receiver secrets only to the API, never worker/frontend configuration.
- Document configuration and rotation without enabling ordinary commercial admission.

**Invariants / Non-goals**

No default bundle changes, fixture-JSON handler, database dependency in the manifest path,
data reset or broader runtime isolation program. No AccessSnapshot/invalidation endpoints.

**Verification**

Add focused manifest/security tests plus:

- `create_app()` and `create_app(bundles=None)` retain the standard registry.
- Explicit temporary bundles load through real ConfigLoader.
- Explicit composition does not mutate defaults; a subsequent default app still contains
  all six products.
- API/worker/config-validator default bundle parity remains intact.
- Ordinary output includes disabled products and both disabled metrics.
- `401`, `403`, safe `5xx`, rotation/revocation, browser refusal and secret-free errors.
- Wrong direction/environment/regional credentials are rejected.
- RU runtime scope, public runtime-config and deployment activation regressions.
- An explicitly configured future-zone fixture does not require an RU-only code branch;
  it does not prove a deployed EU runtime.

Run relevant focused API/deployment tests, config/architecture guards and changed-file
Ruff checks.

**Expected completion**

After this step, the real API serves the private RU manifest and supports isolated
configuration through its factory while preserving standard composition.

**AI execution prompt**

```text
Implement Step 2 of the canonical ANY-711 plan.

Repository: /home/wstanley/www/work_unirec/runtime-research/anytoolai-platform.
Baseline: feature/ANY-711 with completed Step 1.

Read API main/bootstrap/settings/dependencies/errors/schemas,
runtime-config router, activation handling, region configuration,
scope-dependent fixtures and base/production Compose documentation.

Add optional bundles to create_app and forward it unchanged to build_runtime.
Omitted bundles and explicit None must preserve default composition;
explicit bundles must retain existing replacement semantics.
Test unchanged standard composition and absence of global-default mutation.

Implement the authenticated complete manifest endpoint, trusted anytoolai/ru
configuration, scoped Bearer authorization/rotation, safe errors, browser
refusal and internal CORS exclusion. Preserve activation and guest behavior.
Ordinary configuration must expose disabled entries without automatically
enabling commercial admission.

Run focused factory/composition, manifest/security and relevant runtime
regressions, existing bundle-parity/config/architecture checks and Ruff.
Prove real ConfigLoader use, complete 200, configured auth 401,
authorization 403 and safe producer failures.

Work only in the repository/directories and baseline specified by this step. Follow each affected repository's root and applicable subtree AGENTS.md files, ARCHITECTURE.md and its actual coding/workflow/testing instructions. In Kernel, include docs/agent/coding-conventions.md and the applicable harness documentation. In Portal, use the applicable docs/engineering conventions, workflow and testing documents where present. Do not assume Portal-specific documentation paths exist in Kernel. Respect architectural layers, typing, error handling, transaction ownership, dependency direction and established project structure.

Implement only the specified step of the single canonical ANY-711 plan stored in Kernel. Reuse existing components and preserve the accepted Portal contract, isolated-zone model, approved test vocabulary and functional outcome. Do not broaden the scope, start subsequent steps or implement paid access/usage accounting. Do not rewrite the existing Portal client without a demonstrated compatibility need.

Run appropriate formatters, linters and focused automated tests. Fix failures caused by your changes and rerun affected checks. Run additional relevant validation when necessary; report unexecuted or blocked checks accurately.

If a material contradiction appears, investigate the relevant surrounding context and available evidence, then propose a resolution. Stop and ask only when an important decision cannot be made safely.

Do not run mutating operations against real billing or other external production systems without explicit authorization. Use only authorized isolated local test resources; do not stop unrelated stacks, reset active development databases, expose secrets or deploy to a shared stand/production.

Do not stage, commit, push, switch branches, merge or rebase. Do not modify unrelated worktrees or publish PRs/ticket updates. Report a baseline mismatch; do not silently change Git history to resolve it.

Report the implemented behavior, changed files, verification results, remaining limitations and any required manual QA.
```

**Proposed commit**

`ANY-711 - Serve authenticated RU capability manifest`

### Step 3 — Publish and verify the producer contract

**Goal**

Make Kernel the durable manifest contract authority with generated schema and independent
compatibility evidence.

**Expected behavior**

Schema/OpenAPI describe the actual response model. Generated JSON remains valid JSON;
Markdown retains its source headers. Independent fixtures detect wire, reference and digest drift.

**Read before implementation**

- **Repository / Working directory:** Kernel; Portal remains read-only reference.
- **Baseline:** `feature/ANY-711` with completed Steps 1–2.
- **Prerequisites:** working endpoint and projection tests.
- Read API `openapi/generate.py`, `scripts/agent/docs_generation.py`,
  `tests/test_docs_generation.py`, CE-kit generation scripts and Portal v1
  schema/fixtures/checker under `docs/contracts/kernel-capability-manifest/v1/`
  and `scripts/check_kernel_manifest_contract.py`.

**Implementation**

- Generate `docs/generated/capability-manifest-v1.schema.json` from the actual API
  response model in its response/serialization form.
- Add it to existing generation and freshness checking.
- Adapt `tests/test_docs_generation.py`: both this schema and `openapi.json` are
  parsed as JSON and have no Markdown header requirement.
- Preserve source-header checks for Markdown outputs.
- Verify deterministic rendering, artifact freshness and correspondence with the response
  model and OpenAPI success schema, resolving reference-layout differences explicitly.
- Create Kernel-owned contract documentation, positive/negative fixtures and checksums.
- Retain the approved Portal positive fixture bytes and independent semantic digest.
- Distinguish byte hashes from semantic versions; check the existing Portal copy.
- Regenerate affected OpenAPI and generated API types using existing tools.
- Update Kernel contract/config/integration navigation without rewriting historical evidence.

**Invariants / Non-goals**

No handwritten competing schema, runtime fixture imports, shared package, additional wire
fields or Portal application changes. No prices, purchased quantities or presentation metadata.

**Verification**

```bash
.quick-check-venv/bin/python -m pytest -q tests/test_docs_generation.py
.quick-check-venv/bin/python scripts/agent/runner.py generate-docs
.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check
.quick-check-venv/bin/python scripts/agent/runner.py validate-docs
pnpm --dir packages/frontend/ce-kit run generate-api-types
pnpm --dir packages/frontend/ce-kit run generate-api-types:check
```

Also verify negative fixtures, independent digest pins, material-change sensitivity,
timestamp/order stability and default-disabled output. Invalid producer configuration
refusal and deliberately corrupt consumer test payloads must be identified separately.

**Expected completion**

After this step, actual response models, generated JSON Schema, OpenAPI and canonical
fixtures have reproducible correspondence and drift checks.

**AI execution prompt**

```text
Implement Step 3 of the canonical ANY-711 plan.

Write only in Kernel:
 /home/wstanley/www/work_unirec/runtime-research/anytoolai-platform.
Read-only Portal reference:
 /home/wstanley/www/work_unirec/runtime-research/payments-portal.
Baseline: feature/ANY-711 with Steps 1–2.

Read API response/OpenAPI generation, scripts/agent/docs_generation.py,
tests/test_docs_generation.py, CE-kit generation and Portal v1 artifacts.

Generate the manifest schema from the actual response model and integrate
its freshness check. Adapt generation tests so the schema and openapi.json
remain valid header-free JSON. Preserve Markdown source-header checks.
Test deterministic generation and response-model/OpenAPI correspondence
with resolved references.

Publish Kernel-owned fixtures/checksums, retain the approved positive
fixture bytes and independent semantic digest, and verify the existing
Portal copy without modifying its application code. Regenerate affected
artifacts and run focused contract/docs/type-generation checks and Ruff.

Work only in the repository/directories and baseline specified by this step. Follow each affected repository's root and applicable subtree AGENTS.md files, ARCHITECTURE.md and its actual coding/workflow/testing instructions. In Kernel, include docs/agent/coding-conventions.md and the applicable harness documentation. In Portal, use the applicable docs/engineering conventions, workflow and testing documents where present. Do not assume Portal-specific documentation paths exist in Kernel. Respect architectural layers, typing, error handling, transaction ownership, dependency direction and established project structure.

Implement only the specified step of the single canonical ANY-711 plan stored in Kernel. Reuse existing components and preserve the accepted Portal contract, isolated-zone model, approved test vocabulary and functional outcome. Do not broaden the scope, start subsequent steps or implement paid access/usage accounting. Do not rewrite the existing Portal client without a demonstrated compatibility need.

Run appropriate formatters, linters and focused automated tests. Fix failures caused by your changes and rerun affected checks. Run additional relevant validation when necessary; report unexecuted or blocked checks accurately.

If a material contradiction appears, investigate the relevant surrounding context and available evidence, then propose a resolution. Stop and ask only when an important decision cannot be made safely.

Do not run mutating operations against real billing or other external production systems without explicit authorization. Use only authorized isolated local test resources; do not stop unrelated stacks, reset active development databases, expose secrets or deploy to a shared stand/production.

Do not stage, commit, push, switch branches, merge or rebase. Do not modify unrelated worktrees or publish PRs/ticket updates. Report a baseline mismatch; do not silently change Git history to resolve it.

Report the implemented behavior, changed files, verification results, remaining limitations and any required manual QA.
```

**Proposed commit**

`ANY-711 - Publish manifest contract and compatibility fixtures`

### Step 4 — Prove real HTTP interoperability with an isolated Portal client

**Goal**

Demonstrate Functional DoD using the real Kernel endpoint and existing Portal client
without working-environment contamination.

**Expected behavior**

A Kernel-owned harness starts the real API with complete temporary configuration, then
invokes Portal's existing typed client in a fresh isolated subprocess. It verifies ordinary
disabled output and the approved enabled test scenario.

No Portal application, database, worker, webhook or LBX stack is started.

**Read before implementation**

- **Kernel directory:**
  `/home/wstanley/www/work_unirec/runtime-research/anytoolai-platform`;
  implementation writes belong here.
- **Portal directory:**
  `/home/wstanley/www/work_unirec/runtime-research/payments-portal`;
  sources and tracked artifacts remain read-only.
- **Baseline:** completed Steps 1–3 on `feature/ANY-711` and rechecked compatible Portal head.
- **Prerequisites:** Portal dependencies prepared with
  `python3.12 scripts/repo.py sync-api` from Portal root, using existing lock and `.venv`.
- Read factory/bootstrap/runner, canonical artifacts, Portal settings import-time loading,
  source composition, client/preflight lifecycle and existing test-setting helpers.

**Implementation**

#### Real Kernel producer

- Add one bounded `runner.py manifest-conformance` harness.
- Accept explicit `--portal-root` and `--portal-python` for consumer execution;
  fail clearly if the required peer environment is absent.
- Copy the complete kernel configuration and all five bundle product roots into temporary storage.
- Enable only the approved ProposalAI/Brief Decoder declarations in those copies.
- Call `create_app(config_root=..., bundles=...)`; let real `build_runtime()`
  and ConfigLoader validate and compose them.
- Serve the actual Kernel router/middleware over an ephemeral loopback TCP port.
- Do not replace the endpoint, parser, response model or HTTP transport with fixture implementations.
- Verify standard composition separately using ordinary application construction.
- Sanitize the producer environment before import/startup as well; do not inherit working
  database/provider credentials.
- Bound readiness, requests, retries and process cleanup; stop only harness-owned resources.

#### Portal isolation before first import

Implement a test-only consumer bootstrap owned by the Kernel harness:

1. Start a fresh subprocess with an allowlisted environment. Do not inherit application,
   LBX, SMTP, Sentry or service credentials.
2. Load the existing stdlib-only Portal test-setting helper before importing
   `app.core.settings`, source composition or the client.
3. Apply synthetic `DEFAULT_API_TEST_ENV` values and explicit safe overrides.
   Disable `BILLING_WORKER_ENABLED` and `LBX_WEBHOOK_ENABLED`; clear LBX URL,
   credentials, signing secret, seller and webhook authentication.
4. Before the first Portal settings import, use a scoped standard-library test patch to
   suppress `dotenv.load_dotenv`. Also wrap the original `BaseSettings.__init__`
   during the probe so `_env_file=None` is forced even for the module's import-time
   singleton. Delegate all validation to the original constructor; do not replace
   Settings or the client.
5. Construct the probe's explicit configuration through the existing test helper with
   `_env_file=None`, real loopback Kernel URL, test token,
   `kernel_mock_enabled=false`, and `anytoolai/ru`.
6. Assert both the import-time singleton and explicit configuration have worker/webhook
   disabled and no LBX configuration. Assert source composition creates no LBX client.
7. Run the unchanged client/preflight lifecycle; restore test patches in `finally`
   and terminate the isolated process.

The `_env_file=None` override disables Pydantic dotenv loading; suppressing the separate
explicit `load_dotenv` call is also necessary.
See [Pydantic dotenv documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/#dotenv-env-support).

Do not rely solely on environment cleanup, working-directory changes, later settings
replacement or settings-source filtering.

Add an isolation regression with a synthetic poisoned dotenv and read spies covering both
loading paths. It must fail if dotenv content is read or can populate global/passed settings.
Never read, rewrite or rename the developer's actual `.env`.

Apply this bootstrap before any Portal imports in focused consumer regression execution
as well. It changes only test-process setup; it does not rewrite Portal application code
or weaken client validation.

#### Joint verification

- Compare actual registry and decoded client inventory: six products and both exact
  metric/owner/unit declarations.
- Check complete disabled ordinary output and enabled test output.
- Verify scope, references and independent digest.
- Exercise auth/scope failures, revoked token, safe producer failures and recovery.
- Check material changes, timestamp/order/restart stability, concurrent calls and retries.
- Instrument the request path to prove no storage/provider calls.
- Keep corrupt-payload fault injection separate from actual producer behavior.
- Record exact producer/consumer SHAs, commands and outcomes. Separate real local
  producer/client HTTP, simulated vocabulary, injected faults, deployed TLS and
  production commercial approval.

#### Reproducible manual QA

Keep the default command automated and self-cleaning. Add narrow modes to the same harness:

- `--mode serve-test`: starts only the real Kernel with the complete isolated test
  configuration and remains available until interrupted.
- `--mode probe`: invokes the existing isolated Portal client against an explicitly
  supplied loopback Kernel origin.

Both manual modes use the same newly generated disposable secret supplied through
`ANY711_CONFORMANCE_TOKEN`. Never print it or pass it in CLI arguments/URLs.

The serving mode prints only its bound URL and nonsecret configuration/evidence metadata.
Probe mode requires the explicit Portal root/interpreter. No generic deployment launcher
is introduced.

Update Kernel integration/deployment instructions with these exact procedures, actual
results and remaining gates. Historical simulated evidence remains unchanged.

**Invariants / Non-goals**

No Portal source changes, working `.env` reads, migrations, running database,
full Portal/LBX stack, purchases, AccessSnapshot, invalidation, usage or quota debits.

**Verification**

Automated check from Kernel root:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

Manual serving terminal, with a disposable `ANY711_CONFORMANCE_TOKEN` supplied
in its environment:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --mode serve-test
```

Manual probe terminal, with the same disposable secret and the printed origin
substituted below:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --mode probe \
  --kernel-base-url http://127.0.0.1:<printed-port> \
  --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

Run existing `apps/api/tests/test_kernel_manifest_client.py` and
`apps/api/tests/test_source_composition.py` regressions through the same pre-import
isolation bootstrap. Record exact commands, SHAs and results without exposing
settings or credentials.

**Expected completion**

After this step, the unchanged Portal typed client consumes the actual Kernel endpoint
over HTTP with complete vocabulary, correct scope/digest and safe failures.
Operators can reproduce the test configuration and client probe independently.

**AI execution prompt**

```text
Implement Step 4 of the canonical ANY-711 plan.

Write implementation only in Kernel:
 /home/wstanley/www/work_unirec/runtime-research/anytoolai-platform.
Portal source reference and consumer execution:
 /home/wstanley/www/work_unirec/runtime-research/payments-portal.
Baseline: feature/ANY-711 with Steps 1–3 and rechecked Portal compatibility.

Before verification, prepare Portal's canonical .venv from Portal root using
python3.12 scripts/repo.py sync-api. Use its existing lock; do not run
migrations, create apps/api/.venv or start a database/Portal/LBX stack.
Portal source read-only restrictions permit this local environment creation.

Read create_app/build_runtime/runner and canonical artifacts; Portal
import-time settings loading, existing test-setting helpers, source
composition, client and preflight lifecycle.

Build the bounded real-HTTP harness. Load complete temporary configuration
through create_app(config_root=..., bundles=...) and real ConfigLoader.
Use the real router/middleware; never return fixture JSON from a replacement
endpoint. Prove ordinary complete disabled output and the approved enabled
two-product test configuration, retaining all six products and both metrics.
Prove that standard application composition remains unchanged.

Before the first Portal settings/client import, establish synthetic settings
and block both explicit load_dotenv and Pydantic dotenv loading using the
scoped test-only bootstrap specified in the plan. Preserve original Settings
validation and client code. Disable workers/webhooks and LBX configuration.
Add a poisoned-dotenv/read-spy regression. Apply isolation to focused Portal
client/source regression execution as well.

Verify scope, references, independent digest, auth/scope/rotation failures,
safe recovery, restart/version behavior and side-effect-free concurrency.
Add serve-test and probe modes to the same harness for reproducible manual QA;
use an environment-only disposable token and never expose it.

Run the HTTP harness, isolation regressions, focused consumer tests and
final Kernel checks. Update only Kernel's contract/integration/handoff docs.
Record actual SHAs and PASS/FAIL/NOT_RUN; separate real local code/HTTP,
simulated vocabulary, injected faults, deployed TLS and production approval.

Work only in the repository/directories and baseline specified by this step. Follow each affected repository's root and applicable subtree AGENTS.md files, ARCHITECTURE.md and its actual coding/workflow/testing instructions. In Kernel, include docs/agent/coding-conventions.md and the applicable harness documentation. In Portal, use the applicable docs/engineering conventions, workflow and testing documents where present. Do not assume Portal-specific documentation paths exist in Kernel. Respect architectural layers, typing, error handling, transaction ownership, dependency direction and established project structure.

Implement only the specified step of the single canonical ANY-711 plan stored in Kernel. Reuse existing components and preserve the accepted Portal contract, isolated-zone model, approved test vocabulary and functional outcome. Do not broaden the scope, start subsequent steps or implement paid access/usage accounting. Do not rewrite the existing Portal client without a demonstrated compatibility need.

Run appropriate formatters, linters and focused automated tests. Fix failures caused by your changes and rerun affected checks. Run additional relevant validation when necessary; report unexecuted or blocked checks accurately.

If a material contradiction appears, investigate the relevant surrounding context and available evidence, then propose a resolution. Stop and ask only when an important decision cannot be made safely.

Do not run mutating operations against real billing or other external production systems without explicit authorization. Use only authorized isolated local test resources; do not stop unrelated stacks, reset active development databases, expose secrets or deploy to a shared stand/production.

Do not stage, commit, push, switch branches, merge or rebase. Do not modify unrelated worktrees or publish PRs/ticket updates. Report a baseline mismatch; do not silently change Git history to resolve it.

Report the implemented behavior, changed files, verification results, remaining limitations and any required manual QA.
```

**Proposed commit**

`ANY-711 - Verify isolated real Portal Kernel manifest interoperability`

## 6. Final Verification & Review

Require evidence for:

- Real registry/config → actual HTTP endpoint → unchanged typed Portal client.
- All six products, both approved metrics, exact owners/units, `anytoolai/ru`
  and independent digest.
- Complete ordinary output including disabled entries; no automatic commercial enablement.
- Approved positive test configuration loaded through the factory and ConfigLoader.
- Unchanged default bundle composition.
- `401`, `403`, safe `5xx`, token rotation/revocation and browser refusal.
- Startup refusal of invalid configuration and no partial `200`.
- Consumer rejection of malformed/incomplete payloads and digest/reference failures.
- Semantic version sensitivity and timestamp/order/restart stability.
- Side-effect-free concurrent reads/retries and failure recovery.
- Pre-import dotenv isolation, safe singleton/explicit settings, and disabled
  worker/webhook/LBX paths.
- Deterministic valid JSON Schema, artifact freshness and actual model/OpenAPI correspondence.
- Preserved guest quota/idempotency, public runtime-config, worker composition and activation.

After implementation, run the supported final canonical checks:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py full-check
.quick-check-venv/bin/python scripts/agent/runner.py validate-docs
.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check
```

Use required PostgreSQL/runtime smoke checks for affected scope behavior through authorized
disposable resources or CI. These are separate regression checks, not prerequisites for the
database-free producer/client HTTP harness. The repository's `postgresql-check`,
`atoms-proof` and production Compose smoke gates retain their actual environment requirements.

Review architectural boundaries, secrets, generated artifacts and unrelated changes.
Obtain final semantic review and resolve findings before acceptance.
Record exact `PASS`, `FAIL`, `NOT_RUN` or `BLOCKED` results.
Do not infer current-head success from historical evidence or silently skipped tests.

Actual deployed TLS/network controls and production metric approval remain separately
unproven unless performed. No deployment or real financial operation is part of this plan.

## 7. Handoff to Next Step

Keep one compact handoff in this canonical Kernel plan and contract/integration documentation:

- Actual producer branch/commit and consumer SHA.
- Endpoint, generated schema/OpenAPI, fixture/checksum locations and digest rules.
- Complete ordinary disabled vocabulary and approved isolated test configuration.
- Optional factory `bundles` behavior and proof of unchanged defaults.
- Trusted RU settings, service-secret configuration and rotation/revocation procedure.
- Portal preparation command, canonical `.venv` and explicit statement that no
  DB/migrations/full stack are needed for conformance.
- Pre-import isolation procedure covering both dotenv paths.
- Automated check and manual `serve-test`/`probe` commands, disposable token handling
  and cleanup.
- Actual results and remaining operational/production gates.
- Confirmation that Portal application changes were unnecessary, or an explicitly
  demonstrated narrow incompatibility with its owner.

Preserve the agreed request directions:

- Portal → Kernel manifest: implemented by this ticket.
- Portal → Kernel invalidation: future operation requiring explicit authorization.
- Kernel → Portal AccessSnapshot: separate receiver credential and future implementation.

Preserve ownership boundaries:

- ANY-765: accepted quantities/cycles and paid projection.
- ANY-766: AccessSnapshot, invalidation, authenticated paid execution, durable usage
  and quota enforcement.
- ANY-767: full paid journey and launch acceptance.
- ANY-282: broader runtime regional isolation.
- ANY-768: infrastructure/runtime deployment work.

These review amendments change neither the accepted architecture nor ANY-711 scope.
Do not repeat Phase 0, relabel historical simulation or create an additional approval framework.
