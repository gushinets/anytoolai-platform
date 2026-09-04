# Execution Plan: ANY-339 Restore PydanticAI Typed Output Binding for Structured Actions

## Status

- State: active
- Owner: agent
- Created: 2026-09-04 (backfilled — implementation, two `/code-review xhigh` rounds, and one PR
  review round had already landed before this file existed; PR review "me #2" flagged the same
  "no exec plan for non-trivial work" gap `docs/exec-plans/active/any-338-propagate-core-closed-enums.md`'s
  own round-3 review previously caught for ANY-338).
- Last updated: 2026-09-04
- Review date: 2026-09-04
- Next action: none — implementation, `/code-review xhigh` rounds 1-2, and PR review rounds "me #1"
  / "team lead #1" / "me #2" all addressed; move to `completed/` once merged.
- Blocker: none

## Goal

`PydanticAIStructuredRunner` built its PydanticAI `Agent` with `output_type=str` unconditionally,
regardless of whether `request.response_schema` was set, and applied the config-owned JSON Schema
entirely inside a custom `@agent.output_validator` that manually parsed the raw string, validated
it, and stashed the result on a side channel (`ctx.deps.parsed_output`) instead of returning it as
PydanticAI's own typed output. This left the active response schema unbound from PydanticAI's
output contract, contrary to ADR 0007
(`docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`) and `docs/architecture/llm-runtime.md`'s
"Structured-output ownership" section. Bind the active config-owned JSON Schema into PydanticAI's
structured output path for schema-backed requests via
`PromptedOutput(StructuredDict(schema), template=False)`, consume the typed mapping result
directly, and keep schema-less requests on the existing text-output path — while preserving every
other invariant (AnyToolAI final validation before persistence, Provider Gateway as the only
transport path, one ledger row per physical attempt, hidden LiteLLM retries disabled).

## Scope

### In scope

- `pydanticai_runner.py`: branch `output_type` on `request.response_schema` — `str` when unset,
  `PromptedOutput(StructuredDict(schema), template=False)` when set.
- `pydanticai_runner.py`: `_validate_output` re-validates each attempt's **raw** provider text
  (`ctx.deps.last_response.output_text`) against the platform's canonical
  `validate_structured_output`, converting `StructuredOutputError` to `ModelRetry` — not PydanticAI's
  own already-parsed `data`, which is more lenient than the platform's strict final parser (see
  Decision log).
- `pydanticai_runner.py`: consume `result.output` directly as
  `PydanticAIValidationResult.structured_output` when schema-bound, instead of the removed
  `ctx.deps.parsed_output` side channel.
- `pydanticai_runner.py`: fail fast with a clear `RuntimeError` naming the `action_config_id` when a
  config schema cannot be bound as PydanticAI output, narrowed to the two exception shapes that
  actually signal an unbindable schema (`pydantic_ai.exceptions.UserError`, `KeyError`) rather than
  a bare `except Exception`.
- New `packages/backend/platform-actions/tests/test_pydanticai_runner.py` — runner-level behavioral
  regression tests, including a `model_request_parameters.output_mode`/`.output_object.json_schema`
  assertion proving schema binding behaviorally (not via source-text assertions).
- Extended `test_structured_llm_executor.py` and
  `packages/backend/platform-core/tests/unit/test_structured_output_validator.py` regression
  coverage for the divergence-class bugs found in review (markdown-fenced responses, malformed
  schemas).
- This exec plan (backfilled per PR review "me #2").

### Out of scope

- `executor.py`, Provider Gateway, ledger/budget code, or `_finalize_response` — untouched; AnyToolAI's
  final-validate/normalize/persist pipeline continues to consume raw provider text independently of
  what the runner returns.
- A permanent Pydantic model hierarchy for config schemas.
- Removing action-specific cross-validators or AnyToolAI final validation.
- Moving PydanticAI into Platform Core.
- Changing Provider Gateway transport ownership or provider policy/retry semantics.
- A second LiteLLM `response_format` validation path.
- Client/agent caching by stable key (`docs/architecture/llm-runtime.md`'s "Client lifecycle" gap;
  the issue scopes this change to the runner/executor output-binding boundary only).
- Reworking unrelated action executors or product schemas.

## Relevant docs

- `plans/ANY-339.md` (issue + implementation plan + all review rounds, gitignored — local-only, not
  part of the git history).
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`, `docs/architecture/llm-runtime.md`.
- `docs/architecture/structured-output.md` — platform must not rely on prompt-text parsing
  heuristics or loose JSON probing.
- `docs/agent/coding-conventions.md` — "catch only expected exceptions; re-raise anything else."

## Contracts touched

- API: none.
- DB: none.
- Config: none (config-owned JSON Schemas under `configs/kernel/schemas/*.json` are read, not
  changed).
- Events: none.
- Frontend: none.
- Internal: `PydanticAIValidationResult.structured_output` is now sourced from PydanticAI's typed
  `result.output` (schema-bound) or the raw string (schema-less), replacing the removed
  `ctx.deps.parsed_output` side channel. `Agent[PydanticAIValidationState, str]` becomes
  `Agent[PydanticAIValidationState, Any]` to accommodate both branches.

## Implementation steps

- [x] `pydanticai_runner.py`: branch `output_type` on `request.response_schema`
      (`d67e90f`).
- [x] `pydanticai_runner.py`: consume `result.output` instead of the `ctx.deps.parsed_output` side
      channel (`d67e90f`).
- [x] New `test_pydanticai_runner.py` with `output_mode`/`output_object.json_schema` behavioral
      assertions (`d67e90f`).
- [x] `/code-review xhigh` round 1 (2026-09-03) — confirmed two issues: PydanticAI's
      `ObjectOutputProcessor` strips markdown fences before validating, but `executor.py`'s
      `_finalize_response` re-parses the same raw (unstripped) text via `parse_strict_json`, so a
      fenced response PydanticAI accepts can crash uncaught downstream; and `StructuredDict(schema)`
      raises an unhandled `UserError` for a schema missing top-level `"type": "object"`. Fixed by
      mirroring fence-stripping in the shared parser and converting the `UserError` into a clear
      `RuntimeError` (`cb2ceb0`).
- [x] `/code-review xhigh` round 2 (2026-09-03, on the round-1 fix) — reproduced two more instances
      of the same divergence class: bare `NaN`/`Infinity` accepted by pydantic-core/jsonschema but
      rejected by `parse_strict_json`; and an old-style `definitions`/`$ref` schema (vs `$defs`)
      raising a raw `KeyError` from pydantic's JSON-schema generator during `Agent` construction,
      outside the round-1 fix's `try/except`. Fixed by rejecting non-finite constants in
      `validate_structured_output_value` and widening the `try/except` around `Agent` construction
      (`072dcb0`).
- [x] PR review "me #1" (GitHub PR #100 inline comments) — blocker: round-1/round-2's leniency
      fixes (`validator.py`'s markdown-fence stripping and empty-string-to-`{}` coercion) went the
      wrong direction — `executor.py`'s `_finalize_response` always re-derives `structured_output`
      from raw text through that same shared parser, so loosening it only weakened the one shared
      strict gate instead of reconciling two paths, silently letting through responses ANY-339
      requires to enter PydanticAI's retry loop. Fixed by reverting `validator.py` to its strict
      baseline and making `_validate_output` independently re-validate each attempt's raw text
      against that same strict validator, converting failures to `ModelRetry` (`65aff07`). This also
      subsumed round 2's `NaN`/`Infinity` fix, making the dedicated `_reject_non_finite` guard
      redundant — removed.
- [x] PR review "team lead #1" — blocker: the schema-binding `try/except` around `Agent`
      construction caught bare `Exception`, violating `docs/agent/coding-conventions.md`'s "catch
      only expected exceptions; re-raise anything else." Narrowed to `(UserError, KeyError)`, the
      two exception shapes confirmed (by direct reproduction against the installed `pydantic_ai`
      2.2.0) to signal an unbindable schema; existing focused tests for both shapes already covered
      this without needing new cases (`0d6013c`).
- [x] PR review "me #2" — comment: confirmed the "team lead #1" catch-narrowing fix closed that
      blocker with no new runtime defect found; process blocker — no execution plan existed under
      `docs/exec-plans/active/` for this non-trivial runtime-boundary change. Backfilled as this
      file.

## Validation

- [x] `python scripts/agent/runner.py quick-check` — run after each fix round; last run 1186
      passed, 399 deselected.
- [x] `python scripts/agent/runner.py validate-architecture` — passed.
- [x] `packages/backend/platform-actions/tests/test_pydanticai_runner.py` — 8 passed (including the
      two schema-binding-failure regression tests exercising the narrowed catch).
- [x] `packages/backend/platform-actions/tests/test_structured_llm_executor.py` against a local
      throwaway PostgreSQL container — 20 passed.
- [x] `python scripts/agent/runner.py postgresql-check` — full pass across platform-core,
      platform-actions, platform-api, platform-worker.
- [ ] `python scripts/agent/runner.py full-check` — not yet run this round; no frontend-relevant
      files changed since the last `full-check`-covered commit.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-03 | `PromptedOutput(StructuredDict(schema), template=False)`, not `output_type=StructuredDict(schema)` alone. | The runner's `FunctionModel` intercept only ever returns plain `TextPart`, never `ToolCallPart`, but PydanticAI's default structured-output mode is `'tool'`. `PromptedOutput` makes PydanticAI parse the schema out of plain text instead of expecting a tool call. `template=False` avoids injecting a second, differently-worded schema instruction on top of the LiteLLM adapter's own `_schema_guidance_message`. |
| 2026-09-03 | Round-1 fix mirrored PydanticAI's markdown-fence stripping inside the platform's shared `validator.py`, then round-1-of-PR-review reverted that and instead made the runner's output validator re-check raw text against the unmodified strict validator. | Reverting was correct: `executor.py`'s `_finalize_response` always re-derives `structured_output` from raw text via the same shared parser, so loosening that parser didn't reconcile two independent validation paths — it just weakened the one path both share, letting fenced/malformed responses through without spending PydanticAI's retry budget, in violation of `docs/architecture/structured-output.md`'s no-heuristic-parsing policy and ANY-339's own retry acceptance criteria. Re-validating raw text against one unchanged strict parser in both places closes the divergence at its root. |
| 2026-09-03 | The `_reject_non_finite` guard added in round 2 (`072dcb0`) was removed once the raw-text-revalidation fix landed (`65aff07`). | `parse_strict_json` already rejects bare `NaN`/`Infinity` from raw text; once `_validate_output` re-validates raw text through the same strict parser, the dedicated guard became redundant dead code, not a second bug needing its own fix. |
| 2026-09-04 | Narrowed the schema-binding `try/except` to `(UserError, KeyError)` instead of chasing further individual `pydantic_ai` exception types or leaving it as `except Exception`. | Round 2's own reasoning ("chasing individual exception types one at a time is an unbounded game") was superseded by the repo's actual convention (`docs/agent/coding-conventions.md`: catch only expected exceptions, re-raise anything else) once "team lead #1" flagged it as a blocker: a bare `except Exception` would mislabel a real `TypeError`/assertion/future regression as a config-schema defect. Reproduced both exception shapes directly against the installed `pydantic_ai` 2.2.0 to confirm no third shape was silently being relied upon. |
| 2026-09-04 | Backfilled this exec plan after implementation and three review rounds, rather than blocking further review on writing it first. | Same precedent as `docs/exec-plans/active/any-338-propagate-core-closed-enums.md`: PR review "me #2" found no exec plan existed under `docs/exec-plans/active/`, per `CLAUDE.md`'s "before coding" requirement. Code was already implemented, reviewed three times, and committed by the time this was caught; backfilling preserves the validated work instead of discarding it for no correctness benefit. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-03 | Implemented schema binding (`d67e90f`): branched `output_type`, dropped the `parsed_output` side channel, added `test_pydanticai_runner.py`. | Await code review. |
| 2026-09-03 | `/code-review xhigh` round 1 found and fixed 2 confirmed divergence-class bugs (markdown fences, unguarded `UserError`). Committed `cb2ceb0`. | Await round-2 review. |
| 2026-09-03 | `/code-review xhigh` round 2 found and fixed 2 more instances of the same class (`NaN`/`Infinity`, old-style `$ref`/`definitions` raw `KeyError`). Committed `072dcb0`. | Open PR. |
| 2026-09-03 | Opened PR #100; fixed its metadata-validation gate (unfilled template body). | Await PR review. |
| 2026-09-04 | PR review "me #1": reverted round-1/round-2's parser leniency, made the runner re-validate raw text against the unchanged strict validator instead — closes the divergence at its root and subsumes the `NaN`/`Infinity` fix. Committed `65aff07`. | Await re-review. |
| 2026-09-04 | PR review "team lead #1": narrowed the schema-binding `except Exception` to `(UserError, KeyError)`. Committed `0d6013c`. | Await re-review. |
| 2026-09-04 | PR review "me #2": confirmed the catch-narrowing fix closed that blocker with no new defect; blocked instead on this exec plan not existing. Backfilled as this file. | Move to `completed/` once merged. |

## Open questions

- None.

## Follow-up debt

- Duplicated cross-validation between the runner's output validator and `executor.py`'s
  `_finalize_response` predates this PR (`executor.py` was not touched) and is not this ticket's
  scope to clean up.
- Schema-shape validation (`type: object`, resolvable `$ref`) only happens at first live call, not
  at `validate-configs` CI time — a malformed config schema would only surface when an action
  actually runs. Flagged in `/code-review xhigh` round 2 as non-blocking; a dedicated
  `validate-configs`-time check would need its own ticket.
- `PromptedOutput(StructuredDict(schema), ...)` is rebuilt on every `run()` call rather than cached
  per `action_config_id`; `docs/architecture/llm-runtime.md`'s "Client lifecycle" section already
  tracks this as a known gap, explicitly out of scope for this ticket.
