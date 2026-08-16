# Execution Plan: ANY-305 Validator Ref Config Registry

## Status

- State: active
- Owner: agent
- Created: 2026-08-14
- Last updated: 2026-08-14
- Review date: 2026-08-14
- Next action: none — implementation and two rounds of review-finding fixes landed; move to
  `completed/` once merged.
- Blocker: none

## Goal

Stop `apps/platform-worker/src/anytoolai_platform_worker/composition.py` from wiring
`StructuredLlmActionExecutor.output_cross_validators` / `ActionRunner.input_validators` as
hardcoded per-`action_type` dict literals. Make validator wiring config-declared and
load-time-enforced, so a new atom that forgets its validator entry fails loudly (at config load
or worker startup) instead of silently running unvalidated.

## Scope

### In scope

- `cross_validator_ref` / `input_validator_ref` required string fields on `ActionDefinition`
  (`platform-core`), with `"none"` as the explicit no-validator sentinel.
- `platform-core` config loader: parse and require both fields, opaque (no cross-reference
  validation against real classes — that would violate the `platform-core` → `platform-actions`
  layering ban).
- `platform-actions`: new `cross_validation/registry.py` resolving refs to concrete validator
  classes, failing closed with `ValidatorRefNotFoundError` on an unresolvable ref.
- `apps/platform-worker/composition.py`: build the validator maps from `ActionDefinition`s instead
  of hardcoding them.
- All 11 `configs/kernel/action_definitions/*.yaml` carrying explicit refs.
- `packages/backend/platform-sdk/contracts/action.py` — mirrored the two fields (not originally
  scoped, but required to keep `test_kernel_demo_configs_parse_into_sdk_contracts` and
  `test_core_models_mirror_sdk_contract_field_names` passing).

### Out of scope

- `docs/architecture/llm-runtime.md` — unrelated to validator wiring.
- `docs/tech-debt-tracker.md` TD-010 — the 4 atoms with no validator class yet stay `"none"`/`"none"`.

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/architecture/package-layering.md`
- `plans/ANY-305.md` (issue + implementation plan + code review findings)

## Contracts touched

- Config: `ActionDefinition` gains `cross_validator_ref` / `input_validator_ref` (required).
- Wire contract: `platform-sdk` `ActionDefinition` mirrors the same two fields.
- Tests: `test_config_loader.py`, `test_action_runner.py`, new `test_cross_validator_registry.py`.

## Implementation steps

- [x] Add `cross_validator_ref` / `input_validator_ref` to `platform-core` `ActionDefinition`.
- [x] Loader: parse, require (fail closed via `InvalidConfigShapeError`), pass through.
- [x] New `platform-actions/structured_llm/cross_validation/registry.py`:
      `build_output_cross_validators` / `build_input_validators` / `ValidatorRefNotFoundError`.
- [x] `composition.py`: replace hardcoded dicts with the two builder calls.
- [x] Update all 11 `configs/kernel/action_definitions/*.yaml` with explicit refs.
- [x] Mirror the two fields onto the `platform-sdk` `ActionDefinition` contract (test-driven, not
      in the original plan scope).
- [x] Tests: missing-`cross_validator_ref` loader test, `test_cross_validator_registry.py`
      (known ref, `"none"` skip, unknown ref, real-config-tree smoke test), `_build_runner` swap.
- [x] Docs: `docs/architecture/action-model.md` required-fields list + `"none"` sentinel note.
- [x] Code review (2026-08-14, commit `e1ee37c`) found 3 gaps, all fixed:
  - Validators were resolved lazily inside the per-job `runner_factory` closure instead of once at
    `build_worker` startup, so a bad ref would only surface on the first job of that action_type
    (swallowed by `RunWorkflowHandler.handle()`'s catch-all) instead of blocking worker boot.
    Fixed: `build_output_cross_validators`/`build_input_validators` now run once in `build_worker`,
    right after `registry` is built.
  - `input_validator_ref` had no symmetric "missing required field" regression test (only
    `cross_validator_ref` did). Fixed: added
    `test_loader_fails_on_missing_action_input_validator_ref`.
  - No exec plan existed under `docs/exec-plans/active/` for this non-trivial, multi-package,
    fail-closed-behavior change, per CLAUDE.md's "before coding" requirement. Fixed: this file.
- [x] Code review rerun (2026-08-14, after startup-validation fix) found 3 more gaps, all
  addressed:
  - Decision log overclaimed parity with `provider_policy_ref` (that resolves against config data
    with no Python class dict at all; validator refs resolve to classes, so `registry.py`'s dict
    literals are the practical minimum, not full parity). Fixed: corrected the decision-log entry
    to state the tradeoff accurately instead of overclaiming.
  - `loader.py`'s `all([...])` check conflated an explicit YAML `null` for
    `cross_validator_ref`/`input_validator_ref` with an omitted field, producing a misleading
    "missing required field" error for someone who wrote `null` meaning "no validator" instead of
    the required literal `"none"`. Fixed: added a targeted pre-check in `_load_action_definitions`
    that raises a specific "`<field>` is null ... use `\"none\"`" error before the generic
    all([...]) check runs, plus `test_loader_gives_specific_error_for_explicit_null_validator_ref`
    in `test_config_loader.py`.
  - Nothing asserted `build_worker(...)` actually fails closed against a real, broken config.
    Fixed: added `test_build_worker_fails_closed_on_unresolvable_validator_ref` to
    `apps/platform-worker/tests/test_worker_boot.py`, mutating a real loaded registry's
    `cross_validator_ref` to an unknown value and asserting `ValidatorRefNotFoundError`.
- [x] Post-merge verification (2026-08-14, after merging `main` which landed ANY-255's
      `text.compare_and_classify` implementation) found the merge had silently reintroduced the
      exact failure mode this issue targets, plus dead code from the 3-way merge:
  - ANY-255 (merged separately into `main`) added real `CompareAndClassifyCrossValidator` /
    `CompareAndClassifyInputValidator` classes, but `main`'s pre-ANY-305 `composition.py` still
    wired them the old hardcoded way. The merge's textual 3-way resolution kept `composition.py`'s
    import of those two classes but dropped their old dict-literal usage (superseded by this
    branch's builder calls), leaving them imported-but-unused -- and, more importantly, leaving
    `text.compare_and_classify`'s YAML at `cross_validator_ref: none` / `input_validator_ref: none`
    and `registry.py`'s lookup dicts without an entry for it. The atom now has real validator
    classes on `main` but silently runs unvalidated on this branch -- exactly the bug ANY-305
    exists to prevent, reintroduced by the merge itself.
    Fixed: added `text.compare_and_classify` to `_CROSS_VALIDATORS`/`_INPUT_VALIDATORS` in
    `registry.py`, changed its YAML refs from `"none"` to `"text.compare_and_classify"`, updated
    `test_cross_validator_registry.py`'s real-config-tree smoke test's expected sets.
  - The same 3-way merge left 10 dead concrete-validator-class imports (all 8 pre-existing classes
    plus the 2 new `CompareAndClassify*` ones) in both `composition.py` and
    `test_action_runner.py` -- the merge re-added the whole old import block from `main`'s side
    without noticing this branch had already replaced all direct-class usage with the
    `build_output_cross_validators`/`build_input_validators` builder calls. Fixed: trimmed both
    files' imports down to just the two builder functions.
- [x] Code review round 3 (2026-08-14) found 2 more gaps, both addressed:
  - `build_output_cross_validators`/`build_input_validators` duplicated the same resolve-or-raise
    loop, risking behavior drift between the two if one were changed and not the other. Fixed:
    extracted a shared `_resolve_validators(action_definitions, *, ref_getter, lookup, field_name)`
    helper in `registry.py`; both public builders now call it with their own ref getter/lookup.
  - Only `cross_validator_ref` had a null-vs-missing regression test; `input_validator_ref` (same
    symmetric loop in `loader.py`) had none. Fixed: added
    `test_loader_gives_specific_error_for_explicit_null_input_validator_ref` in
    `test_config_loader.py`.

## Validation

- [x] `python scripts/agent/runner.py quick-check`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_config_loader.py packages/backend/platform-core/tests/unit/test_action_runner.py packages/backend/platform-actions/tests/test_cross_validator_registry.py packages/backend/platform-actions/tests/test_structured_llm_executor.py packages/backend/platform-core/tests/unit/test_workflow_runner.py`
- [x] `python scripts/agent/runner.py validate-configs` / `validate-architecture`
- [x] Manual fail-closed sanity check: deleted `cross_validator_ref` from a real YAML, confirmed
      `validate-configs` fails, restored the line.
- [x] Re-run `quick-check` after the post-review hoisting/test fixes to confirm still green.
- [x] Re-run `quick-check` after the second review round (null-vs-missing loader message,
      `build_worker` fail-closed test, decision-log correction) to confirm still green.
- [x] Re-run `quick-check` after the third review round (shared `_resolve_validators` helper,
      `input_validator_ref` null-ref test) to confirm still green.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-14 | `cross_validator_ref`/`input_validator_ref` are opaque strings in `platform-core`, resolved only in `platform-actions`. | `platform-core` must never import `platform-actions` (`docs/architecture/package-layering.md`). Loosely inspired by `provider_policy_ref`, but not the same depth: `provider_policy_ref` resolves against config data (`ConfigRegistry.get_provider_policy()`), no Python class dict involved. Validator refs resolve to concrete validator *classes* (behavior, not data), so `registry.py`'s `_CROSS_VALIDATORS`/`_INPUT_VALIDATORS` dict literals are unavoidable short of dynamic import-by-string — a strictly worse tradeoff for 8 known classes (reflection risk, no static "does this class exist" check). What this design does eliminate: the YAML can no longer *silently* omit a validator (loader fails closed), and a bad ref fails at worker startup, not first job. The Python-side ref→class table still needs a matching edit when adding a validator; that's accepted, not hidden. |
| 2026-08-14 | Ref value is the `action_type` string itself, or `"none"` — no separate namespace. | No case today of one validator serving multiple atoms; a distinct namespace would be speculative (YAGNI). |
| 2026-08-14 | Also update `platform-sdk`'s `ActionDefinition` contract, despite the original plan marking it out of scope. | Existing tests (`test_kernel_demo_configs_parse_into_sdk_contracts`, `test_core_models_mirror_sdk_contract_field_names`) construct/compare it against real config and the core dataclass; leaving it out broke `quick-check`. |
| 2026-08-14 | Hoist `build_output_cross_validators`/`build_input_validators` calls out of the per-job `runner_factory` closure into `build_worker`. | Code review: lazy per-job resolution meant a bad ref only surfaced on first job of that action_type, silently persisted as a job failure instead of blocking worker startup — defeats the "fail closed at composition-root construction time" design goal. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-14 | Implemented per `plans/ANY-305.md`'s design: model field, loader enforcement, `platform-actions` registry module, `composition.py` swap, all 11 YAML files, `platform-sdk` contract fix, tests, docs. `quick-check` green (570 passed), targeted suite green (65 passed / 57 skipped), fail-closed sanity check confirmed. Committed as `e1ee37c`. | Await/act on code review. |
| 2026-08-14 | Code review found 3 gaps (lazy startup resolution, missing symmetric test, no exec plan). Fixed all three: hoisted validator-map construction into `build_worker`, added the missing `input_validator_ref` loader test, filed this exec plan. | Re-run `quick-check` and targeted suite to confirm the fixes are green, then commit. |
| 2026-08-14 | Rerun code review found 3 more gaps (overclaimed `provider_policy_ref` parity, misleading null-vs-missing loader error, no real fail-closed `build_worker` test). Fixed all three: corrected the decision log, added a targeted null-check with a clearer message in `loader.py`, added `test_build_worker_fails_closed_on_unresolvable_validator_ref`. | Re-run `quick-check` and targeted suite, commit. |
| 2026-08-14 | Round-3 code review found 2 more gaps (duplicated resolve-or-raise loop across the two builders, missing `input_validator_ref` null-ref test). Fixed both: extracted `_resolve_validators` shared helper in `registry.py`, added the symmetric null-ref test. | Re-run `quick-check` and targeted suite, commit. |
| 2026-08-14 | Merged `main` into `feature/ANY-305` to pick up ANY-255 (`text.compare_and_classify` A11 implementation). Merge silently reintroduced the "forgotten validator wiring" failure mode for `text.compare_and_classify` (new validator classes existed but weren't wired through `registry.py`/YAML) plus left 10 dead imports in `composition.py`/`test_action_runner.py`. Fixed both, updated the smoke-test expected sets. | Re-run `quick-check` and targeted suite, commit. |
| 2026-08-16 | Second `main` merge (bringing in ANY-256 `text.score_match_by_rubric`) reproduced the exact same wiring gap: `ScoreMatchByRubricCrossValidator`/`ScoreMatchByRubricInputValidator` existed and were exported from `cross_validation/__init__.py`, but `registry.py`'s lookup dicts and the YAML refs were left at `"none"`/`"none"`. This time `composition.py`/`test_action_runner.py` conflict resolution kept the builder-function imports cleanly (no dead imports). Wired the new atom through `registry.py` + YAML, updated `test_cross_validator_registry.py`'s expected sets. This confirms the wiring gap is a recurring merge hazard, not a one-off — every `main` merge that lands a new atom with real validator classes needs this check until validator wiring gets a fail-closed test that runs without a live Postgres DB (see note below). | Re-run `quick-check` and targeted suite, commit. |

## Open questions

- None.

## Follow-up debt

- TD-010: 2 action types (`document.generate_from_template`, `text.score_multidimensional_axes`)
  have no validator class yet and carry `"none"`/`"none"`. `text.compare_and_classify` moved off
  this list on 2026-08-14 (ANY-255) and `text.score_match_by_rubric` moved off on 2026-08-16
  (ANY-256), both once their branches landed real validator classes and this branch's merges wired
  them through `registry.py`. When a real validator is added for one of the remaining 2, change its
  YAML ref from `"none"` to the concrete ref — the loader/registry will then demand the class exist.
- Every `main` merge that lands a new atom's validator classes has silently left them unwired
  (`registry.py` dict + YAML ref) twice in a row (2026-08-14, 2026-08-16) — the passing test suite
  didn't catch either because the decisive tests are `pytest.mark.postgresql`-gated and skip
  without a live DB in sandboxed runs. Consider a DB-free unit test that asserts every atom whose
  action definition ships alongside a same-named class in `cross_validation/` is actually present
  in `_CROSS_VALIDATORS`/`_INPUT_VALIDATORS`, so this stops depending on manual post-merge review.
