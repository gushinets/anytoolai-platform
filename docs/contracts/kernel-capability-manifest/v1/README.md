# Kernel Capability Manifest v1

Kernel owns this producer contract and its canonical test fixtures (ANY-711).
The API response model owns wire shape; product YAML declarations loaded into
the composed registry own capability semantics. No runtime imports this directory.

## Generated authority

- [Response model](../../../../apps/platform-api/src/anytoolai_platform_api/schemas.py):
  `CapabilityManifestResponse`, with unknown fields forbidden.
- [JSON Schema](../../../generated/capability-manifest-v1.schema.json): generated
  from that model with `model_json_schema(mode="serialization")`, draft 2020-12.
- [OpenAPI JSON](../../../generated/openapi.json) and
  [operation index](../../../generated/openapi.md): generated from the real application.
  The success schema references `#/components/schemas/CapabilityManifestResponse`.
- [Independent offline checker](../../../../scripts/agent/check_capability_manifest_contract.py)
  and [contract tests](../../../../apps/platform-api/tests/test_capability_manifest_contract.py).

The standalone schema uses `$defs`; OpenAPI uses `components/schemas`.
Tests resolve local references and compare all wire constraints, excluding only
schema-document annotations (`$schema`, titles, descriptions and definition containers).
The retained Portal schema has different definition names but identical resolved constraints.
References may carry the ignored annotations/definition containers listed above. Other sibling
keywords cause an explicit checker failure: their conjunctive constraints are not merged or ignored.
There is no separately handwritten Kernel schema. JSON artifacts have no Markdown
headers; generated Markdown retains its canonical-source header.

## Request and response

```http
GET /internal/v1/capability-manifest?tenant_id=anytoolai&region=ru
Authorization: Bearer <server-side Portal credential>
```

The seven response fields are `schema_version` (integer `1`), `tenant_id`,
`region`, `manifest_version`, `generated_at`, `products` and `usage_metrics`.
Products contain `product_id` and boolean `enabled`. Metrics contain `metric_key`,
`product_id`, `unit` and boolean `enabled`. The timestamp is timezone-aware UTC.
Every registered product and declared metric is returned, including disabled entries.
There is no pagination, filtering, price, purchased quantity or presentation metadata.

JSON Schema covers shape and scalar constraints. Uniqueness, metric ownership,
exact requested scope, digest correctness and completeness against the loaded registry
also require semantic checks. ConfigLoader rejects invalid declarations before serving;
the API never uses these fixtures to construct a response.

Configured authentication failures return `401` with a Bearer challenge;
authenticated authorization failures return `403`. Missing receiver configuration returns
`503`; unexpected producer failure returns a safe `500`. Neither returns a partial `200`.
Errors use Kernel's existing envelope. Browser-origin requests are refused, and the
internal route is excluded from public CORS. See
[receiver configuration and rotation](../../../../infra/deployment/README.md#portal-capability-manifest-receiver-any-711).
Production requires verified TLS and private network controls. Generated CE-kit types
describe the full OpenAPI document; they do not authorize frontend calls to this route.

## Fixtures, byte checksums and semantic versions

[valid-manifest.json](fixtures/valid-manifest.json) retains the approved Portal
positive example **byte for byte**, including array order and timestamp. It describes
six test products with only ProposalAI and Brief Decoder enabled, and the two enabled
TEST-ONLY metrics `proposal_ai.test_generations` (`generation`) and
`brief_decoder.test_analyses` (`analysis`). Its byte SHA-256 is:

```text
25f39800090615eeba04cb27ab020332d0cf7cf7250fac6d2e5c38754c89b354
```

Its independently retained [semantic version pin](fixtures/valid-manifest.digest) is:

```text
sha256:a39bac9f210a6ac67e97e117f8481a5954dc3f36bdaab2fd54c7522b27d6ec29
```

[default-disabled-manifest.json](fixtures/default-disabled-manifest.json) records
the ordinary six-product/two-metric configuration with all flags disabled:

```text
sha256:478761c681d02330ed052aabe5e1b472dc1c2ee56d79a568a8009f4b4503a694
```

[SHA256SUMS](SHA256SUMS) hashes the exact bytes of every file in `fixtures/`;
it is independent of semantic versioning. Semantic versions hash only
`schema_version`, `tenant_id`, `region`, `products` and `usage_metrics` as compact
UTF-8 JSON with unescaped Unicode, recursively sorted object keys, products sorted by
`product_id` and metrics by `metric_key`. They exclude timestamp and digest fields.
Reordering and timestamp changes preserve the version; material field or inventory
changes alter it. Fixtures and pins are reviewed data, not regenerated from runtime hashes.

[invalid-manifests.json](fixtures/invalid-manifests.json) contains deliberately corrupt
consumer payloads: missing/extra fields, unsupported/boolean schema version, nonboolean
flags, invalid/naive timestamps and invalid timezone offsets, duplicate products/metrics,
nonexistent owners, wrong digest and wrong tenant/region. Reference/scope faults retain matching digests
to isolate rejection reasons. These are fault injections, **not possible successful
producer configurations**. Producer refusal is covered separately by ConfigLoader and
manifest startup/security tests; invalid declarations fail configuration loading.

The Portal copy at inspected commit `2bb07d778edc5ea56011b0034ba24b0702ede81f`
has identical positive fixture/digest bytes and equivalent resolved schema constraints.
Its provisional documentation and historical SIMULATED evidence remain unchanged.
Canonical ownership here does not relabel that evidence or approve production metrics,
charging, quantities, purchases or paid execution.

## Reproduce artifact verification

From Kernel root, using the existing managed environment and frontend dependencies:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py generate-docs
.quick-check-venv/bin/python scripts/agent/runner.py generate-docs --check
.quick-check-venv/bin/python scripts/agent/runner.py validate-docs
.quick-check-venv/bin/python -m pytest -q tests/test_docs_generation.py apps/platform-api/tests/test_capability_manifest_contract.py
.quick-check-venv/bin/python scripts/agent/check_capability_manifest_contract.py --portal-root ../payments-portal
pnpm --dir packages/frontend/ce-kit run generate-api-types
pnpm --dir packages/frontend/ce-kit run generate-api-types:check
```

The offline checker requires no Portal imports, environment, database or service.
Omit `--portal-root` for repository-local checks. It reports
`REAL_HTTP_CONFORMANCE=NOT_RUN_BY_OFFLINE_CHECK`; HTTP evidence comes from the
separate real-producer harness below.

## Real Kernel / Portal HTTP conformance

Prepare Portal once, from its repository root, using its existing lock:

```bash
python3.12 scripts/repo.py sync-api
```

This creates the repository-root `.venv`. Do not create `apps/api/.venv` or run
migrations, a database, Portal, billing workers, webhooks or an LBX stack.
Portal tracked sources and artifacts remain read-only. From Kernel root:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

The command fails if explicit peer paths or dependencies are unavailable. It
generates disposable credentials in memory and cleans up only its own processes,
TCP listeners and temporary config copies. It binds an ephemeral `127.0.0.1` port;
local socket permission is required. No Docker or database is needed.

The producer constructs the ordinary app separately. For the enabled scenario it
copies the **complete** kernel config and all five bundle product roots, enables
only ProposalAI/Brief Decoder and their approved test metrics, and calls the real
`create_app(config_root=..., bundles=...)`. ConfigLoader, runtime composition,
router, middleware, response model and TCP HTTP transport remain real. Later
omitted/`None` bundle construction must retain the ordinary composition.

Each Portal probe runs in a fresh subprocess with an allowlisted environment.
Before the first Portal settings/client import, it loads the existing stdlib test
helper and applies `DEFAULT_API_TEST_ENV` plus safe overrides. Scoped stdlib test
patches suppress `dotenv.load_dotenv` and wrap the **original**
`BaseSettings.__init__` to force `_env_file=None`; original Settings validation
still runs. Both singleton and explicit settings have workers/webhooks disabled,
LBX connection/authentication/signing/seller fields empty, and no SMTP/Sentry
configuration. Source composition must create no LBX client. Read guards reject
any `.env` content access in both producer and consumer processes.

The synthetic poisoned-dotenv regression redirects only settings-file path
resolution to a temporary tree. It spies on both dotenv loading paths, confirms
safe global/explicit settings and checks that the read tripwires fire. It never
reads, rewrites or renames a developer `.env`. Patches unwind on failure and the
consumer process terminates. The unchanged client runs through its existing
source/preflight lifecycle with `kernel_mock_enabled=false` and
`CONFIGURED_SOURCE` provenance. Its strict parser independently checks scope,
references and digest.

The default run also executes the existing Portal client/source regressions
through this same pre-import bootstrap. They can be reproduced independently:

```bash
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --mode isolation --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --mode regressions --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

The two existing modules are `apps/api/tests/test_kernel_manifest_client.py` and
`apps/api/tests/test_source_composition.py`. Their corrupt-payload cases use
injected transports and remain separate from real producer HTTP evidence.

## Manual isolated QA

In terminal A, generate a new disposable secret. A private temporary file passes
it between local shells; its **path** is nonsecret. No token value is printed or
put in arguments/URLs:

```bash
ANY711_TOKEN_FILE="$(mktemp /tmp/any711-token.XXXXXX)"
chmod 600 "$ANY711_TOKEN_FILE"
.quick-check-venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))' > "$ANY711_TOKEN_FILE"
export ANY711_CONFORMANCE_TOKEN="$(cat "$ANY711_TOKEN_FILE")"
printf 'Disposable token file path: %s\n' "$ANY711_TOKEN_FILE"
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance --mode serve-test
```

In terminal B, substitute the printed temporary file path and origin. The same
secret enters only the probe's environment. Once both shells have loaded it,
remove the temporary file. A local secret manager can supply the same environment
value instead. Never paste the token into a command, URL, tracked file or log:

```bash
ANY711_TOKEN_FILE=/tmp/any711-token.<printed-suffix>
export ANY711_CONFORMANCE_TOKEN="$(cat "$ANY711_TOKEN_FILE")"
rm -- "$ANY711_TOKEN_FILE"
.quick-check-venv/bin/python scripts/agent/runner.py manifest-conformance \
  --mode probe --kernel-base-url http://127.0.0.1:<printed-port> \
  --portal-root ../payments-portal \
  --portal-python ../payments-portal/.venv/bin/python
```

`serve-test` prints its URL, registry inventory/digest and nonsecret evidence. It
runs only the real test-configured Kernel until interrupted. `probe` checks the
complete enabled test inventory over real TCP using the unchanged Portal client.
It accepts only an explicit `http://127.0.0.1:<port>` origin. Stop the serving
command with Ctrl+C, then `unset ANY711_CONFORMANCE_TOKEN` in each shell. If the
probe was never started, remove the temporary token file from terminal A as well.
Normal automated runs need no secret provisioning or manual cleanup.

## Local evidence, 2026-10-29

Producer: `feature/ANY-711`, base SHA
`7634eb09533846268a96ade004bca518c580b588` plus the uncommitted Step 4 diff.
Consumer: `ANY-715`, SHA `2bb07d778edc5ea56011b0034ba24b0702ede81f`.
Both exact SHAs are printed by automated runs; Portal source/artifacts are unchanged.

- **PASS:** real registry/config → real router/middleware over TCP → unchanged
  typed Portal client, six products, two exact metric/owner/unit declarations,
  `anytoolai/ru`, references and independent digest.
- **PASS:** ordinary all-disabled and approved test-enabled inventories; the
  existing default and positive digest pins above match actual HTTP responses.
- **PASS:** wrong/missing credentials, authenticated wrong tenant/region,
  browser refusal, current/previous token overlap and revocation after restart.
- **PASS:** injected producer dependency failures yield safe correlated `500`,
  bounded client retry/exhaustion and recovery with no partial successful response.
- **PASS:** material metric disablement changes the digest to
  `sha256:46c39e140370c19d0f4dc3914996672cd8bcb080d735a2b27cffbd842fbba221`;
  timestamps, root order, concurrent reads and fresh-process restart preserve
  unchanged semantics. Invalid config refuses startup.
- **PASS:** storage/session/engine and ProviderGateway request instrumentation
  records zero calls across reads, faults, retries and concurrency.
- **PASS:** poisoned dotenv isolation, 92 unchanged Portal client/source
  regressions, and manual serve/probe plus interrupt cleanup.

This is real **local code/HTTP conformance with TEST-ONLY vocabulary**. Historical
SIMULATED mappings/fixtures keep their provenance. Deployed TLS/private-zone
controls, production metric approval, financial behavior and paid execution are
not established. Final Kernel check results and remaining gates are recorded in
the [canonical plan](../../../exec-plans/completed/ANY-711-implementation-plan.md).
