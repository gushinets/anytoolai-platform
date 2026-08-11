# Execution Plan: ANY-252 A07 text.compose_reply Contract And Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-08-11
- Last updated: 2026-08-11
- Review date: 2026-08-10
- Next action: address the "team lead #4" review item this plan resolves (add this file), then
  re-run `quick-check`/`postgresql-check` and continue with any further review rounds.
- Blocker: none

## Goal

Implement the product-neutral `text.compose_reply` atom (legacy A07 `generate_reply`) as a strict,
independently runnable JSON-schema contract — `situation`/`intent`/`tone`/optional `constraints` in,
`text`/optional `call_to_action` out — executed through the existing `StructuredLlmActionExecutor`/
`ProviderGateway`/`ActionRunner`, so ANY-218 can count it toward 11/11 without a placeholder/smoke
qualification.

## Scope

### In scope

- Strict, closed (`additionalProperties: false`) input/output JSON schemas replacing the previous
  fully-permissive placeholders.
- `ComposeReplyCrossValidator`: runtime enforcement of the per-call `constraints.max_length` and
  `constraints.output_format` fields the static output schema cannot express (they vary per call).
- Product-neutral prompt (`compose_reply.v1.md`) and `kernel_demo.compose_reply_v1` product-level
  action config/fake-provider fixture, proving the same platform action type can be configured by a
  product without changing the platform schema.
- Deterministic fake-provider execution through `ActionRunner`, validated output artifact with
  action/provider/artifact event lineage, and a validation-retry proof through the real
  `ProviderGateway`/DB ledger (not only an in-memory spy).
- Focused platform-core/platform-actions test coverage plus config/architecture/docs/quick-check
  gates.

### Out of scope

- Wiring `text.compose_reply` into any Kernel Demo workflow (DoD only requires independent
  ActionRunner runnability for ANY-218, not workflow integration).
- The sibling A20a atoms (`document.generate_from_template` / ANY-253,
  `text.generate_clarifying_questions` / ANY-254).
- `tone_achieved` — explicitly excluded from the v1 contract per the issue description (an
  unverified model self-assessment is not execution evidence).

## Relevant docs

- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none (action-runner atom, not an HTTP endpoint)
- DB: none (uses existing `action_runs`/`provider_calls`/`artifacts`/event tables; no migration)
- Config: `configs/kernel/schemas/compose_reply_{input,output}.schema.json` (now strict),
  `configs/kernel/products/kernel_demo/{prompts,action_configs}.yaml` (new `compose_reply_v1`
  entries), `configs/kernel/products/kernel_demo/prompts/compose_reply.v1.md` (new),
  `tests/fixtures/provider/fake_provider_outputs/kernel_demo.compose_reply_v1.json` (new)
- Events: none new (existing `action.*`/`provider.*`/`artifact.*` event types)
- Frontend: none

## Implementation steps

- [x] Design the input/output JSON schemas (situation/intent/tone-enum/optional constraints ->
      text/optional call_to_action); close outer schemas with `additionalProperties: false`.
- [x] Write the product-neutral prompt `compose_reply.v1.md`.
- [x] Add the `kernel_demo.compose_reply_v1` product-level action config and prompt registration.
- [x] Add the deterministic fake-provider fixture.
- [x] Add `ComposeReplyCrossValidator` (`packages/backend/platform-actions/.../cross_validation.py`)
      for the per-call `constraints.max_length`/`constraints.output_format` checks the static output
      schema cannot express, and register it in the production composition root
      (`apps/platform-worker/.../composition.py`).
- [x] Add ActionRunner tests: deterministic execution with full event lineage, and a
      validation-retry proof through the real `ProviderGateway`/DB ledger (two physical
      `provider_calls` rows with correct semantic/physical indexes).
- [x] Add focused schema boundary tests (missing/empty required fields, unexpected properties,
      enum/range violations, `text`/`call_to_action` length boundaries).
- [x] Add this execution plan (raised by team-lead review #4 — see decision log).
- [ ] Update `docs/architecture/action-model.md` with the finalized A07 contract shape.
- [ ] Regenerate generated action/config documentation (`generate-docs --check`) and confirm it's
      clean with the final schema/config state.
- [ ] Final `quick-check` / `postgresql-check` pass and PR.

## Validation

- [x] `uv run pytest packages/backend/platform-actions/tests/test_cross_validation.py -q`
- [x] `uv run pytest packages/backend/platform-actions/tests/test_compose_reply_schema.py -q`
- [x] `uv run pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `uv run pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `python scripts/agent/runner.py quick-check` (after each review round)
- [x] `python scripts/agent/runner.py postgresql-check` (local Postgres 16 container; covers the
      real-ledger retry test and the worker lease/SIGTERM suite)
- [ ] `python scripts/agent/runner.py generate-docs --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-10 | Cap `constraints.max_length` at the input schema level (`maximum: 4000`) to match the output schema's static `text` cap | A review found a caller-requested `max_length` above 4000 was physically unachievable: the output schema's static `maxLength: 4000` on `text` is enforced in `executor.py::_finalize_response` before the cross-validator ever runs, so a wider caller limit could never be satisfied |
| 2026-08-10 | Enforce the plain-text "no markup" rule whenever `output_format` is `plain_text` **or omitted**, not only when explicitly `plain_text` | The prompt contract says "if it is plain_text or omitted, text must contain no markup"; omitted is a valid, common case per the schema and was originally left unchecked |
| 2026-08-10 | Replace the markup detector with two real `markdown-it-py` `MarkdownIt("gfm-like")` parser instances (one `html=True` for HTML-construct detection via `html_inline`/`html_block` tokens, one `html=False` for CommonMark/GFM markdown-construct detection) instead of a hand-rolled tag-name allowlist or regex | Each prior regex/allowlist iteration was reported as incomplete by review (missed `<script>`/`<kbd>`, missed `<svg>`/`<math>`/custom elements/comments/doctypes, missed markdown tables/code fences/strikethrough); a real tokenizer resolves the whole class by parsing the actual grammar instead of enumerating known constructs |
| 2026-08-10 | Accepted, not fixed: a real HTML tokenizer flags plain bracketed English words like `<Tuesday>` as markup (an unknown/custom element), reversing an earlier allowlist-based fix that had specifically avoided this false positive | This is the same trade-off a browser makes with unknown elements, and was explicitly accepted once review asked for a complete real-tokenizer-based detector over a closed allowlist |
| 2026-08-10 | Escape only alphanumeric-flanked (not just digit-flanked) asterisks before markdown parsing | CommonMark's real emphasis rule allows unspaced `*` to open/close intraword, so `a*b*c`/`L*W*H`/`2*x*4` (variable/symbolic products), not only `2*3*4`, were false-positived as italic emphasis |
| 2026-08-10 | Kept `call_to_action` optional in the output schema (`required: ["text"]` only); declined a review request to make `ComposeReplyOverLimitThenValidAdapter`'s fake responses always include it | Verified directly against the loaded schema and a live re-run of the retry test that the finding's premise (static output validation requires `call_to_action` before the cross-validator runs) does not hold for the current schema; no code change made pending an explicit decision to change the contract itself |
| 2026-08-11 | Added this execution plan retroactively, after most of the implementation and four review rounds had already landed | `AGENTS.md:69-76` requires an execution plan under `docs/exec-plans/active/` for any non-trivial work before coding; team-lead review #4 flagged that no such plan existed for this branch's scope (schemas, cross-validator, dependencies, tests across multiple lockfiles) |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-10 | Implemented strict input/output schemas, prompt, `kernel_demo.compose_reply_v1` config/fixture, `ComposeReplyCrossValidator`, and initial ActionRunner/executor tests | Address first code-review pass (missing cross-validator registration, duplicated test scaffolding) |
| 2026-08-10 | Registered the cross-validator in the composition root; extracted shared `schema_support.py`; fixed the `output_format` omitted-case gap and the `max_length` upper-bound schema gap; added `TestComposeReplyCrossValidator` and schema boundary tests | Address third review pass (HTML/markdown detection false positives and gaps) |
| 2026-08-10 | Replaced the tag-name allowlist and regex-based markdown detector with two `markdown-it-py` parser instances; broadened the arithmetic-asterisk exclusion to alphanumeric; added the real-ledger provider-call retry proof test; regenerated all three affected `uv.lock` files (root, `apps/platform-worker`, `packages/backend/platform-actions`) | Add the execution plan required by `AGENTS.md` (team-lead review #4) |
| 2026-08-11 | Added this execution plan | Update `docs/architecture/action-model.md`, regenerate docs, and run a final `quick-check`/`postgresql-check` pass |

## Open questions

- Should `call_to_action` become a required output field? A review round requested this on the
  premise that the schema already requires it; verification showed it currently does not
  (`required: ["text"]` only). Left as an explicit open design question rather than silently
  changed.

## Follow-up debt

- `docs/architecture/action-model.md` has not yet been updated with the finalized A07 contract
  shape; generated action/config documentation has not yet been regenerated/checked against the
  final schema state.
