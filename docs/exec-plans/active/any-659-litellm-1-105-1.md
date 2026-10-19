# Execution Plan: ANY-659 Upgrade LiteLLM to 1.105.1

## Status

- State: active
- Owner: agent
- Created: 2026-10-16
- Last updated: 2026-10-19
- Review date: 2026-10-19
- Next action: open the PR; move to `completed/` once merged.
- Blocker: none. ANY-656 (PR #170) is merged into `main`, and this branch has merged `main`.

## Goal

Pin the LiteLLM SDK to 1.105.1 in every Python project, keep the ANY-656 Provider Gateway behaviour
(`reasoning_effort` passthrough, temperature handling, structured output), keep LiteLLM hidden
retries off, and record the PydanticAI decision.

## Scope

### In scope

- `litellm==1.105.1` in the root and `platform-core` `pyproject.toml`; `uv lock` in all five
  projects (root, `apps/platform-api`, `apps/platform-worker`, `platform-core`, `platform-actions`).
- Wire-level tests: the real SDK over a mocked HTTP transport
  (`platform-core/tests/unit/test_litellm_adapter.py::test_litellm_wire_*`, helper in
  `tests/unit/providers/litellm_wire.py`, inside the ATAI006 provider boundary).
- `docs/architecture/llm-runtime.md` "Dependencies and pinning": the pin, the transitive additions,
  the PydanticAI decision.

### Out of scope

- PydanticAI upgrade and aligning its versions across lock files (root 2.2.0, api 2.40.0, worker
  2.9.0): a separate ticket.
- Removing `allowed_openai_params`: kept as the guard for the next model the registry lacks.
- ANY-676/678/679/680 vulnerabilities: only their lock-file overlap is noted below.

## Resolver diff

Identical in all five lock files, nothing else moved:

- `litellm` → 1.105.1 (from 1.89.3 root/core/actions, 1.92.0 api, 1.91.2 worker);
- added `boto3`/`botocore` 1.43.114, `s3transfer` 0.19.2, `jmespath` 1.1.0, `python-dateutil`
  2.9.0.post0, `six` 1.17.0, `h2` 4.4.1, `hpack` 4.2.0, `hyperframe` 6.1.0, `pydantic-settings`
  2.16.0;
- api, worker, core, actions only: `aiohttp` 3.14.1 → 3.14.5, `yarl` 1.24.2 → 1.25.1 (root already
  had `aiohttp` 3.14.3). This touches ANY-679's package: check its CVE range before closing it.
- unchanged: `openai` (2.43.0 / 2.45.0), `pydantic` 2.13.4, `httpx` 0.28.1, `pydantic-ai-slim`.

## Decisions

- **PydanticAI is not upgraded.** It is not a LiteLLM dependency and the resolver needed no change.
  Our PydanticAI code is a `FunctionModel` that calls ProviderGateway, so it never sees LiteLLM.
- **Model catalog is unaffected.** `LiteLLMModelCatalogSource` fetches LiteLLM's metadata JSON from
  GitHub at refresh time, not from the installed SDK, so the SDK version does not change it.
  `openai_model_capability_overrides.yaml` does not list `gpt-6-luna` / `gpt-6.1-sol`.
- **No new gateway test.** ProviderGateway retries every adapter exception the same way; the
  existing `test_gateway_transport_retry_creates_multiple_rows_with_transport_indexes` proves one
  ledger row per gateway attempt and the new wire test proves one HTTP request per adapter call.

## Verification

Measured on 2026-10-16 against LiteLLM 1.105.1:

- Wire tests: `gpt-6-luna` and `gpt-6.1-sol` × `medium`/`high` send the effort and no temperature;
  `gpt-5.4` and `gpt-5.4-mini` send no effort and no temperature by default, and `none` plus the
  policy temperature at explicit `none`; the default alias sends `gpt-6-luna` at `medium` without
  temperature; a 500 makes exactly one HTTP request on the router and the direct path. A
  `num_retries=2` mutation fails the retry test. LiteLLM still reports `response_cost` for all four
  models.
- Observed: LiteLLM 1.105.1 forwards `reasoning_effort: none` for `gpt-6.1-sol` even without
  `allowed_openai_params`, although its registry marks `none` unsupported; the API decides.
- Installed in the built prod images: api and worker both `litellm 1.105.1`, `aiohttp 3.14.5`,
  `yarl 1.25.1`, `openai 2.45.0`, `pydantic 2.13.4`, `httpx 0.28.1`, `h2 4.4.1`, `boto3 1.43.114`;
  `pydantic-ai-slim` 2.40.0 (api) / 2.9.0 (worker), unchanged. The new transitive packages add
  about 32 MB per image (botocore 29 MB).
- Repository checks (after merging `main`, 2026-10-19): `validate-configs`, `validate-architecture`,
  `validate-docs`, `generate-docs --check`, `postgresql-check` green; `atoms-proof` 11/11 atoms and
  3/3 composite workflows on images rebuilt from this tree (`dev-up` reuses existing images, so a
  stale image can make the proof pass without testing the new SDK: check `litellm` inside the api and
  worker images). The quick-check pytest step had 2341 passed and 1 failed:
  `test_activation_marker_is_readable_by_non_root_api_user`, which needs passwordless `sudo` that the
  sandbox does not have; it does not touch dependencies.
- Live, 2026-10-19, real OpenAI, LiteLLM 1.105.1:
  - `live-canary` on the default alias: 11/11 atoms and 3/3 composites passed. The ledger holds 22
    `provider_calls` rows (one per action run), all `succeeded`, model `gpt-6-luna` through
    `anytoolai.default_text`, no errors, `physical_call_index` and `transport_attempt_index` at most
    1 (no hidden retry), 20,075 tokens, $0.0038, 3.8 s on average. The ledger records the policy
    temperature (1.0) and no effort; the router adds `medium` and the adapter drops the temperature
    on the wire, which only the wire tests show.
  - Direct path through the real adapter, one call per case, every one accepted by the API and made
    with one request: `gpt-6-luna` and `gpt-6.1-sol` at `medium` and `high` send the effort and no
    temperature; `gpt-5.4` and `gpt-5.4-mini` without an effort send neither; `gpt-5.4` at `none`
    sends `none` and temperature 0.2; `gpt-4o` sends temperature 0.2 and no effort.
  - Not run live: the Atom Lab surface of `live-canary` (it needs the access code and the Atom Lab
    compose stack); its request path is the direct one above.
