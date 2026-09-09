# Execution Plan: ANY-227 B02a ProposalAI Bundle And Workflow

## Status

- State: active
- Owner: agent
- Created: 2026-09-08
- Last updated: 2026-09-08
- Review date: 2026-09-08
- Next action: none — implementation landed, `/code-review xhigh` pass #1 findings addressed;
  awaiting further code review.
- Blocker: none

## Goal

Define the ProposalAI product bundle and its strict single-run A06 (`text.compose_persuasive_text`)
workflow as the first real product root inside `FreelancerSuiteBundle`
(`packages/backend/product-platforms/freelancer-suite`), proven through the real composition path
and the real worker, with no Platform Core, atom-contract, or mapping-DSL change.

## Scope

### In scope (implemented)

1. **Product directory** —
   `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/proposal_ai/`:
   `product.yaml`, `scenarios.yaml`, `workflows.yaml`, `action_configs.yaml`, `prompts.yaml` +
   `prompts/compose_persuasive_text.v1.md`, `schemas.yaml` + `schemas/generate_input.schema.json`,
   `quotas.yaml`, `frontends.yaml`. No `handoffs.yaml`/`analytics.yaml` — nothing in the ticket
   names a handoff target or a custom event.
2. **Bundle wiring** — `FreelancerSuiteBundle.config_roots()`
   (`freelancer-suite/src/anytoolai_freelancer_suite/bundle.py`) returns
   `[.../products/proposal_ai]`, replacing the ANY-32 empty list.
3. **Fake-provider fixtures** — `tests/fixtures/provider/fake_provider_outputs/
   proposal_ai.compose_persuasive_text_v1.json` (happy path) and
   `proposal_ai.compose_persuasive_text_v1.weak_input.json` (weak-input variant, selected
   explicitly by fixture name in product-level tests since the real runtime never sets a
   `fixture_key` — see Design decision 4).
4. **Tests** — `apps/platform-api/tests/test_proposal_ai_bundle.py` (quick-check, SQLite harness,
   real `create_app`/`build_worker`) and
   `packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py`
   (full-check, raw YAML/JSON only, no `anytoolai_platform_core` import per ATAI007/ATAI008).
   Updated `freelancer-suite/tests/test_bundle_loads.py` (ANY-32's "zero product roots" assertion
   no longer holds) and `README.md` roadmap line.

### Out of scope

`apps/web-mirror` page/renderer, Chrome Extension (ANY-235), browser QA (ANY-243), custom backend
endpoints, a live-provider action-config variant, any A06 atom-contract or mapping-DSL change, any
other Freelancer Suite product.

## Design decisions

1. **Mapping-DSL workaround, resolved without a wrapper schema field.** The ticket's literal spec
   (`context.task_text <- scenario.input.task_text`, `context.freelancer_positioning <- ...` as
   *separate* target keys) is illegal: `_parse_target_path` in
   `platform-core/.../workflows/mappings.py` rejects any input-mapping target whose first dotted
   segment is `context` when the target has more than one segment (empirically confirmed).
   Instead of nesting the two fields into a new `proposal_context` wrapper object in the product
   schema (the workaround an unmerged sibling branch, `feature/ANY-413`, uses for the same A06
   shape), this bundle maps the *entire* scenario input object into `context` in one entry:
   `context: scenario.input` (source path `scenario.input` with no further segments resolves to
   the whole input dict; target `context` is a single segment, which the DSL allows). This keeps
   the product input schema flat and matches the ticket's literal field names
   (`task_text`, `freelancer_positioning`, `tone`, `language`) exactly, with no new wrapper object
   and no mapping-DSL change. `tone`/`language` land in `context` too, which A06's `context` field
   (`additionalProperties: true`) tolerates; they are also mapped separately into
   `constraints.tone`/`constraints.language`, which is what the atom actually reads.
2. **Defaults (`tone: warm`, `language: en`) are prompt-level, not runtime-injected.** Neither the
   `jsonschema` validator this repo uses (`structured_output/validator.py`,
   `workflows/runner.py`) nor the mapping DSL's `?`-prefix (which only *omits* an absent key, it
   never substitutes a value) fills in a JSON Schema `default`. Building a default-injection
   mechanism would be new platform-core behavior, which is out of scope and unnecessary here: the
   product's own prompt (`prompts/compose_persuasive_text.v1.md`) instructs the model to default
   to a warm tone / English when `constraints.tone`/`constraints.language` are absent from its
   input. `tone`/`language` stay optional (not required-with-schema-default) in
   `generate_input.schema.json`.
3. **Quota `limit_count`.** The ticket requires an explicit `limit_count` but does not name a
   number. Set to `3`, mirroring `kernel_demo.guest_quota_v1`. Revisit if product/business picks a
   different guest-quota budget for ProposalAI specifically.
4. **Weak-input fixture selection.** The real runtime path (`ActionRunner` → provider gateway →
   `FakeProviderAdapter`) never sets `ResolvedProviderRequest.fixture_key`; the fake provider
   always falls back to `action_config_id`, so an *unmodified* HTTP scenario run cannot select a
   second fixture for the same `action_config_id`. Revised after code review: rather than leaving
   the weak fixture disconnected from any real workflow run, `test_proposal_ai_bundle.py` now
   has a test-only `_FixedFixtureProviderAdapter` (a `FakeProviderAdapter` subclass, confined to
   the test file) that forces `fixture_key` on the resolved request before delegating to the real
   adapter — no product or platform runtime change. That test
   (`test_proposal_ai_weak_input_end_to_end_produces_the_checked_in_weak_fixture_artifact`) proves
   the checked-in weak fixture is schema-valid *and* genuinely reachable end to end, asserting the
   canonical result against the fixture file's own content. The pre-existing
   `test_proposal_ai_product.py` fixture-shape assertions and the unmodified
   `test_proposal_ai_weak_but_non_empty_input_still_passes_schema_and_completes` (proving the
   pipeline's *natural* fixture resolution still completes for a vague input) remain as
   complementary evidence — the schema-level rejection of *empty* input is covered separately.

## Required evidence

- `python scripts/agent/runner.py validate-configs` — passed.
- `python scripts/agent/runner.py validate-architecture` — passed.
- `apps/platform-api/tests/test_proposal_ai_bundle.py` (5 tests) — real `build_runtime`/
  `build_worker`, SQLite-backed: happy path (A06 invoked exactly once, `copy_result` allowed,
  canonical `{"text": ...}` result), weak-but-non-empty input still succeeds, and three
  empty/whitespace-input cases each fail with `workflow_input_validation_failed` and zero
  `provider_calls` rows.
- `packages/backend/product-platforms/freelancer-suite/tests/test_proposal_ai_product.py`
  (9 tests) — action-type sequence, no forbidden provider/model tokens anywhere in the product
  directory, quota-policy-ref resolution, mapping-DSL-legality of every `input_mapping` entry,
  fixture/output-schema agreement (both fixtures), weak-input-fixture distinctness, input-schema
  field contract.
- `python scripts/agent/runner.py quick-check` / `full-check` — to run before PR.

## `/code-review xhigh` pass #1 (2026-09-08) — disposition

Full findings are in `plans/ANY-227.md`. Fixed:

- **Regex bug** (`language` pattern used `$`, which Python `re` matches just before a trailing
  `\n`, so `"en\n"` passed validation) — `generate_input.schema.json` now uses `(?!\n)$`.
  (An initial fix used `\Z`, but that isn't valid ECMA-262 syntax — the dialect JSON Schema's
  `pattern` keyword is defined against — so a later review round replaced it with `(?!\n)$`,
  which closes the same gap under Python's `jsonschema` while staying portable.) Regression test:
  `test_language_pattern_rejects_a_trailing_newline`.
- **Misleading test name/docstring** on the weak-input worker test — renamed to
  `test_proposal_ai_weak_but_non_empty_input_still_passes_schema_and_completes` with a docstring
  stating exactly what it does and doesn't prove (it can't exercise the `.weak_input.json` fixture
  itself — see Design decision 4 above).
- **Prompt gap**: `context` carries the whole scenario input (including `tone`/`language`, per
  Design decision 1), but the prompt only documented `task_text`/`freelancer_positioning`. Added
  an explicit "ignore `context.tone`/`context.language`" line.
- **Stale docstrings** in `tests/architecture/test_bundle_composition_parity.py` still claiming
  `DEFAULT_PRODUCT_BUNDLES` contributes zero `config_roots` — updated to explain why the
  fixture-bundle proof is still needed now that a real product exists.
- **Redundant config parsing**: platform-api tests built a second, independent `ConfigRegistry`
  per `build_worker()` call instead of reusing the one `create_app()` already built. Added
  `_build_worker(app, session_factory)` passing `config_registry=app.state.runtime.config_registry`.
- **Weak anti-hallucination regex** only matched digit-form counts (`4 years`), not the
  spelled-out form the happy fixture itself uses (`four years`) — broadened to match both.
- **Packaging test only proved one-level nesting** — `test_packaging.py`'s fixture product now
  also has a `prompts/*.md` and `schemas/*.json` file, matching ProposalAI's real two-level shape.
- **Duplicated SQLite test harness** (finding #10 — also answers the "split into reusable modules"
  ask): `test_demo_api.py` and `test_proposal_ai_bundle.py` had byte-identical `session_factory`
  fixtures. Moved to `apps/platform-api/tests/conftest.py`; both files now get it for free by
  parameter-name matching. `test_scenario_runtime_api.py` keeps its own (Postgres-backed) fixture
  of the same name, which still safely overrides the shared one per normal pytest resolution — left
  untouched since it's a different backend, not the same duplication.

Deliberately not fixed (documented risk, not a regression from this ticket):

- **Guest quota consumed before input-schema validation** (`scenarios/service.py`'s
  `consume_for_accepted_start()` runs at `/start`, before `workflows/runner.py`'s schema check on
  the worker side) is pre-existing, cross-cutting platform behavior, not something ANY-227
  introduced. Fixing it means reordering platform-core's start/validate sequence for every
  product, which is out of this ticket's scope (Platform Core changes are explicitly not required
  here) and needs its own ticket. Effect: three whitespace-only submissions in a row exhaust the
  lifetime guest quota with zero successful results — worth flagging to product/whoever owns the
  quota UX, not silently absorbing into this PR. Correction (round 3 review): `limit_count: 3,
  period: lifetime` is not a ProposalAI-specific choice that makes this worse than elsewhere --
  `configs/kernel/products/kernel_demo/quotas.yaml` uses the identical `limit_count: 3, period:
  lifetime`. This is an existing repo pattern this PR followed (Design decision 3), not a new,
  more-exposed configuration; the underlying mechanism risk is real but not unique to this PR.
- **`context: scenario.input` mapping-DSL workaround** (Design decision 1) — review flagged this,
  together with the unmerged `feature/ANY-413` needing a different workaround for the same atom,
  as a signal the DSL's `context.*` restriction is worth fixing at the root. Out of scope here:
  the ticket explicitly forbids a mapping-DSL change for this issue.
- Not treated as bugs: `constraints.length: 'literal:4000'` matching A06's own `maxLength: 4000`
  in two independent places is the ticket's own instruction (cap at 4000, matching the atom's max),
  not an accidental duplication needing a shared constant; no `*_live_v1` action config is
  explicitly out of scope per this exec plan already.

## `/code-review xhigh` passes #2 and #3 (2026-09-08 / 2026-09-09) — disposition

Full findings are in `plans/ANY-227.md`. Pass #2 scoped to the ANY-227 commit itself; pass #3
re-verified everything, refuted one pass-#2 finding, and refined two pass-#1 findings. Fixed:

- **Anti-hallucination regex still had a gap** (pass #3): matched `"4 years"` and `"four years"`
  but not the hyphenated compound-adjective form (`"4-year"`, `"three-week"`) — live repro
  confirmed. Pattern now allows a hyphen (or no separator) between the number and the unit.
- **`FORBIDDEN_PROVIDER_TERMS` duplication** (pass #1 finding #7, sharpened in pass #3 finding #5
  with a concrete precedent: `test_bundle_composition_parity.py` already dynamic-loads
  `scripts/agent/validate_configs.py` as a module for the same reason). The provider-name half of
  the list now comes from `validate_architecture.py`'s own `LLM_PROVIDER_IMPORTS` via the same
  dynamic-import pattern, instead of a second hand-maintained copy that could silently drift from
  the one `ATAI006` actually enforces; the model-string prefixes (`gpt-`/`claude-`/`gemini-`) stay
  local since they're raw text, not an import name, with no central list to reuse.
- **Stale test count in this doc** (pass #2 finding #2): "(7 tests)" corrected to the real,
  `--collect-only`-verified count above.

Corrected framing (not a code change, a documentation correction):

- **Quota risk severity** (pass #3 finding #1): pass #1 framed the lifetime `limit_count: 3` as
  something that hits ProposalAI harder than `kernel_demo`. Reviewed and found inaccurate --
  `kernel_demo.guest_quota_v1` uses the identical `limit_count: 3, period: lifetime`. See the
  corrected note under "Deliberately not fixed" above.

Deliberately not fixed (repo-wide pattern, not introduced by this ticket):

- **`app` fixture rebuilds `create_app()`/`build_runtime()` from scratch per test** (pass #3
  finding #6, new): all 5 tests in `test_proposal_ai_bundle.py` each pay a full config parse via
  the `app` fixture, the same class of cost `_build_worker` already avoids for the worker side.
  Not fixed here: `test_demo_api.py` has the identical per-test `app` fixture shape and predates
  this PR -- this is an existing repo convention (function-scoped fixtures, not a shared
  session-scoped registry), not something ANY-227 introduced. Changing fixture scope repo-wide is
  a bigger, cross-cutting change than this ticket's evidence gate calls for.

Reviewed and refuted (pass #3 finding #7, retracting pass #2 finding #3):

- **Duplicated `_request` httpx helper** across `test_proposal_ai_bundle.py` and
  `test_demo_api.py` -- pass #2 called this PR-specific duplication. Pass #3 re-checked and found
  the same helper shape repeated across 6+ files in `apps/platform-api/tests/`: a pre-existing,
  repo-wide convention, not something this PR introduced or should uniquely fix.

## Code-review (blocking, from the PR author's own account) — disposition

Full findings are in `plans/ANY-227.md` ("Code-review (me #1)"). All three verified against
current code and fixed -- these were genuine truthfulness-contract violations, not style nits:

- **Happy fixture invented an unsupported delivery commitment.** The response promised "a first
  draft ready within the first week" and a no-ramp-up claim, neither grounded in the task's
  two-week deadline or the positioning's "4 years" experience claim. Rewritten to restate only the
  input's own facts (the two-week timeline, four years of experience) and end on a scope-setting
  call, with no new commitment invented.
- **Weak fixture invented a claim about the freelancer's usual process** ("here's how I typically
  work: a discovery step, a draft, then revisions") that the extremely vague input ("I build
  websites.") never stated. Rewritten to acknowledge only the stated fact and ask clarifying
  questions instead of asserting an unstated process.
- **The checked-in weak fixture was never actually reachable by any test through the real
  pipeline** (`FakeProviderAdapter` only ever resolves `fixture_key` from `action_config_id`, so
  every existing test necessarily got the happy fixture) -- it could be wrong, as it was, while
  every test still passed. Added a test-only `_FixedFixtureProviderAdapter` in
  `test_proposal_ai_bundle.py` (a `FakeProviderAdapter` subclass confined to the test file, no
  product/platform runtime change) that forces `fixture_key` on the resolved request, plus a new
  test asserting the real workflow's canonical result matches the weak fixture file's own content.
- Also strengthened the regression coverage the review asked for: the existing weak-input
  anti-invention check only caught fabricated *quantities* (a year/week/day regex), not a
  fabricated commitment or process claim. Added
  `test_fixtures_make_no_delivery_or_process_commitment_the_input_never_stated`, a denylist check
  run against *both* fixtures (the happy one is just as capable of inventing an unsupported
  commitment as the weak one).

## Resolved follow-up

None outstanding for this ticket. Web page implementation is ANY-243; Chrome Extension is the
optional ANY-235.
