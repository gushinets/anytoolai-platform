# Execution Plan: ANY-90 Artifact Correlation Follow-up

## Status

- State: completed
- Owner: Codex
- Created: 2026-07-28
- Last updated: 2026-08-05
- Review date: 2026-07-28
- Next action: none; implementation and required validation are complete.
- Blocker: none

## Goal

Preserve every applicable runtime correlation dimension on `artifact.created` across normal
artifact creation and rollback recovery while cleaning up overlapping handoff, quota, migration,
docs, and validation-hardening debt that still affects this replacement PR surface.

## Scope

### In scope

- Canonical artifact metadata helpers and replay reconstruction
- Structured-output, action, and final-workflow artifact correlation propagation
- Safe bounded artifact event metadata only
- Handoff config/runtime consistency fixes that overlap this branch
- Quota recovery helper cleanup without changing established ANY-88/ANY-89 behavior
- Handoff migration deduplication and redundant-index cleanup
- Docs, execution-plan, papercut, and targeted regression updates for still-valid review findings

### Out of scope

- Reordering or redesigning ANY-88 causal replay sequencing
- Reordering or redesigning ANY-89 step-start replay semantics
- Product-specific behavior in the generic artifact layer
- New handoff FK indexes unless a failing query/test proves they are required

## Reviewed

- Core docs: `ARCHITECTURE.md`, `docs/index.md`, MVP scope, core beliefs, platform boundaries,
  package layering, LLM runtime, MVP-A kernel, harness engineering map
- Runtime docs: `docs/architecture/runtime-storage.md`, `docs/architecture/event-taxonomy.md`
- Related work: ANY-15, ANY-88, ANY-89, PR `#23`, closed PR `#40`, current branch state
- Current implementation areas: artifacts, structured output, workflow runner, handoffs, quotas,
  scenarios, migrations, access logging, docs generation, PostgreSQL concurrency tests

## Findings Status

- `artifact.created` correlation replay is still incomplete and still valid.
- Shared artifact metadata string/helper duplication is still present and still valid.
- Mixed-case `/v1/handoffs/` path redaction fallback is still valid.
- Runtime-storage inventory counts are stale and still valid.
- A10 execution-plan accuracy needs a fresh plan file and truthful command recording; still valid.
- Handoff required-field ordering before mapping normalization is still valid.
- Handoff payload schema handling still misses `SchemaError`; still valid.
- Safe handoff error-code allowlist is still too loose for non-ASCII lowercase; still valid.
- PAPERCUTS has duplicate managed-environment notes; still valid.
- Uvicorn access-log regression test should set `access_log=False` directly; still valid.
- PostgreSQL quota concurrency test constants/helpers still need cleanup; still valid.
- Handoff migrations still duplicate DDL and keep a redundant target-session index; still valid.
- Structured handoff ownership/enablement diagnostics still need structured fields; still valid.
- Generic YAML loader still contains handoff-specific duplicate scanning; still valid.
- SafeLoader `# noqa: S506` is still missing; still valid.
- Handoff event source/target selection still uses direct truthiness in one path; still valid.
- Handoff repository mutations are not fully tenant/region scoped; still valid.
- Quota recovery still constructs a throwaway quota service only to emit events; still valid.
- `LinkedScenarioSessionResult.job` is still typed as `Any | None`; still valid.
- Missing-job `result_ready` next-action flow still raises `RuntimeError`; still valid.
- Handoff test-registry replacement still overwrites unrelated handoff definitions in some tests; still valid.
- OpenAPI docs-generation test name still overstates its contract; still valid.
- Full source-artifact revalidation before handoff mapping is already correct and must be preserved.
- Additional handoff FK indexes from earlier review are outside coherent scope unless new evidence appears.

## Implementation Steps

- [x] Review docs, repository state, branch baseline, and prior review history.
- [x] Verify each listed finding against the current branch and classify it.
- [x] Add the shared artifact metadata helper module and route artifact replay through it.
- [x] Expand structured-output persistence context and unify success/debug artifact metadata construction.
- [x] Remove duplicated `_metadata_str` implementations and switch remaining callers to the shared helper, including the provider-gateway event and rollback-recovery paths identified in review.
- [x] Apply handoff/config/runtime hardening updates that remain valid.
- [x] Deduplicate handoff migration DDL and remove the redundant target-session index.
- [x] Update runtime-storage/docs/PAPERCUTS/OpenAPI/exec-plan follow-up accuracy.
- [x] Add or update targeted regression coverage for artifact correlation and still-valid hardening findings.
- [x] Run focused suites, PostgreSQL concurrency coverage, and repository validation commands in the required order.
- [x] Review the PostgreSQL CI checkout behavior; retain the existing head-SHA checkout and diagnostics at the user's direction.
- [x] Address PR review follow-up: preserve the historical 0004/0008 handoff index contract and make the 0009 downgrade exact.
- [x] Address PR review follow-up: assert every applicable debug-artifact correlation dimension.

## Validation

- Historical local `doctor` attempt was blocked by missing system-Python dependencies (`pytest`, `yaml`, `pydantic`); it is not counted as successful validation.
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_artifact_service.py packages/backend/platform-core/tests/unit/test_structured_output.py packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_handoffs.py packages/backend/platform-core/tests/unit/test_runtime_storage.py apps/platform-api/tests/test_access_logging.py tests/test_docs_generation.py -q`
- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `uv run python -m pytest apps/platform-api/tests/test_handoffs_api.py -q`
- Historical local PostgreSQL concurrency attempt skipped because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was unset; it is not counted as successful validation.
- [x] PR #54 required CI ran the canonical `python scripts/agent/runner.py postgresql-check` successfully against PostgreSQL.
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check`
- [x] `python scripts/agent/runner.py quick-check` (passed after rerunning with `PYTEST_ADDOPTS=--basetemp=.quick-check-tmp\\pytest-any90-final` to avoid a locked stale temp directory)
- Historical provider-gateway selection passed its non-database regression but skipped the
  PostgreSQL recovery case without a database URL; the skip is not counted as successful
  validation.
- [x] `python scripts/agent/runner.py validate-architecture`

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-28 | Confirmed the local branch is effectively at `main`, reviewed ANY-15 / PR `#23` / closed PR `#40`, checked for conflict markers, and verified the current set of still-valid follow-up findings. | Create the fresh execution plan file and implement the shared artifact-correlation contract. |
| 2026-07-28 | Ran the first two focused validation slices successfully: artifact/workflow tests and handoff/runtime-storage/access-log/docs tests both passed. | Finish implementation, extend the remaining targeted suites, then run the rest of the validation ladder. |
| 2026-07-28 | Implemented the shared artifact-correlation helper path, expanded structured-output persistence metadata, removed duplicated metadata-string helpers, hardened handoff/config/quota/scenario code paths, deduplicated handoff migration DDL, and updated docs/tests. | Finish the validation ladder and record any remaining external blockers truthfully. |
| 2026-07-28 | Focused artifact/workflow/action suites passed; focused handoff/config/runtime-storage/API/docs suites passed; `validate-configs`, `validate-architecture`, `validate-docs`, `generate-docs --check`, and `quick-check` passed. The PostgreSQL concurrency suite executed as an explicit skip because no disposable PostgreSQL maintenance URL was configured locally. | Report the completed implementation and the PostgreSQL-environment blocker clearly in the final handoff. |
| 2026-07-29 | Began review remediation for merge-result CI coverage, migration-history fidelity, and complete debug-artifact correlation assertions. The required system-Python `doctor` check again reported the known missing `pytest`, `yaml`, and `pydantic` modules; validation will use the repository-managed environment. | Apply the three focused fixes, run targeted tests, then rerun repository validation. |
| 2026-07-29 | Completed all three review fixes. Focused structured-output/runtime-storage/migration tests passed (`51 passed, 1 skipped`); config, architecture, docs, and generated-doc checks passed; canonical `quick-check` passed (`429 passed, 7 deselected`) with a fresh pytest base temp. Full GitHub publishing is paused because the required GitHub CLI is unavailable; the user separately authorized a local commit. | Commit the scoped remediation locally; install and authenticate `gh` before a later push. |
| 2026-07-29 | Restored the PostgreSQL CI job's head-SHA checkout and checkout diagnostics exactly as requested by the user; no runtime workflow code was changed. | Commit the explicit workflow restoration separately; do not push without a new request. |
| 2026-07-31 | Corrected the missed provider-gateway `_metadata_str` copies in normal event construction and rollback recovery so both now use `common.metadata.metadata_str`. | Run focused provider-gateway coverage and architecture validation. |
| 2026-07-31 | Focused canonical-metadata coverage passed for normal provider events; the PostgreSQL-backed replay case remained an explicit skip without a configured test database. Architecture validation and import-order checks passed. | Hand off the scoped review fix. |
| 2026-08-05 | Reconciled historical local skips with PR #54's successful canonical PostgreSQL CI evidence. The plan's implementation and validation scope is complete. | None. |
