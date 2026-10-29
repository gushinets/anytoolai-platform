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
Omit `--portal-root` for repository-local checks. It explicitly reports real HTTP
conformance as `NOT_RUN_STEP_4`. Actual TCP HTTP interoperability with the unchanged
Portal client and reproducible isolated serving/probing belong to Step 4 of the
[canonical plan](../../../exec-plans/active/ANY-711-implementation-plan.md).
