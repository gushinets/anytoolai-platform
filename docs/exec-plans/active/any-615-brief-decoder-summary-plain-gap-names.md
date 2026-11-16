# Execution Plan: ANY-615 Brief Decoder Summary Plain Gap Names

## Status

- State: active
- Owner: agent
- Created: 2026-11-16
- Last updated: 2026-11-16
- Review date: 2026-11-16
- Next action: review the implementation and re-run the full gate in a suitable environment;
  live acceptance on B02/B04/B05 and `asdf ::: 12345 !!!` in Russian, English and Spanish.
- Blocker: three unrelated deployment-runner baseline failures; see Validation.

## Goal

Brief Decoder summaries name missing information in ordinary words in the document's language,
never as machine field keys. Existing facts, readiness rules and the complete-brief branch stay
unchanged.

## Scope

- Map all six extracted brief fields to readable names in the existing v1 summary prompt.
- Prohibit field keys and technical labels in every section and in `summary`.
- Add Python regression checks for reported leaks, ordinary wording, all three summary fixtures
  and the prompt contract, using the existing raw YAML/JSON product test approach.
- Check sibling product prompts for the same instruction.

## Out of scope

ANY-849 input guidance, ANY-850 copy controls, schemas, workflows, DSL, UI, dependencies and live
acceptance runs. No prompt-reference or version changes.

## Risks

Prompt-text and fake-provider fixture tests do not prove live model behavior. QA must re-run
B02 (missing audience), B04 (missing deliverables), B05 (Russian missing audience), and the input
`asdf ::: 12345 !!!`. Live evals should cover Russian, English and Spanish.
The leak guard is a fixture regression check, not a runtime filter or a general language detector.

## Implementation steps

- [x] Run doctor and validate this plan.
- [x] Add and exercise the regression tests, then update the prompt.
- [x] Run quick-check, validate-configs, validate-docs and full-check (baseline blockers below).
- [x] Record evidence and leave live acceptance pending.

## Decision log

- 2026-11-16: use "technical field labels" in the prohibition so the obsolete raw-name
  instruction is absent even from negative examples.
- 2026-11-16: sibling scan found no matching raw-key instruction in ProposalAI or Client Update
  Writer; Acceptance Builder already maps missing entries to readable names. Scope stays local
  to Brief Decoder.

## Validation

- Doctor: system Python 3.14 lacks pytest/pydantic; the managed Python 3.12.13 doctor passes.
  Optional pnpm reports a local database warning under the sandbox.
- Regression before the prompt edit: 12 selected cases passed, the new prompt test failed on
  the obsolete raw-name instruction as expected.
- After the edit: all 43 Brief Decoder product tests passed, including all three summary
  fixtures. The leak guard rejects the QA strings and accepts ordinary English, Russian and
  Spanish wording; these are deterministic tests, not multilingual model evals.
- Quick-check: initial dependency bootstrap needed network access; the network-enabled run
  completed with **4,137 passed, 3 failed, 12 skipped, 717 deselected**. Existing baseline
  selection/skips were unchanged. Config, architecture, docs and generated-doc checks passed.
  Failures in unchanged `tests/test_runner.py`:
  - `test_prod_stack_running_reflects_compose_ps_output`: local production environment-file
    discovery adds a Compose config query, whose mocked response is a container ID, not JSON.
  - `test_prod_stack_running_propagates_timeout`: the same discovery reaches the 60-second
    config query instead of the mocked 10-second stack query.
  - `test_activation_marker_is_readable_by_non_root_api_user`: passwordless sudo to `nobody`
    is unavailable (`interactive authentication is required`).
- Standalone validate-configs: system Python lacks SQLAlchemy; rerun through the managed
  Python 3.12 interpreter passed. Standalone validate-docs passed after adding Review date.
- Full-check with `PYTEST_ADDOPTS=-x`: **313 passed, 1 failed, 717 deselected**; stopped at
  `test_prod_stack_running_reflects_compose_ps_output`, the same baseline failure. Frontend and
  subsequent product stages were not reached. No failures were ignored or marked expected.
- Independent full Freelancer product suite: **273 passed**, including wheel packaging, using
  the managed interpreter and `UV_CACHE_DIR` pointing to the repository's writable cache.
  The initial standalone attempt had 272 passed and one packaging failure using the default
  cache under the sandbox; using the same cache as the canonical runner resolved it.
- Collected sanitized failure context with the repository runner. Final validate-docs and
  whitespace checks passed. No live provider or PostgreSQL acceptance run was performed.
