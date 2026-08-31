# Execution Plan: ANY-25 A22c MVP-A Boundary Audit

## Status

- State: active
- Owner: agent
- Created: 2026-08-31
- Last updated: 2026-08-31
- Review date: 2026-08-31
- Next action: none — implementation and one round of code-review fixes landed; move to
  `completed/` once merged.
- Blocker: none

## Goal

Confirm MVP-B products can be built without changing `platform-core`, per the practical handoff
criterion: a real MVP-B product ships via configs/prompts/schemas/CE wrapper only. Close the AC/DoD
gaps the ticket names explicitly (no product-specific-endpoints test, add-product recipe doc,
MVP-B handoff note) — the import/term/prompt boundary enforcement itself already existed on `main`.

## Scope

### In scope

- New architecture test: no platform-api router hardcodes a Freelancer product path/prefix
  instead of `{product_id}`.
- New architecture test: LiteLLM-format `provider/model` strings appear only in
  `configs/kernel/provider_policies.yaml` / `litellm_router.yaml`.
- `docs/product-specs/add-product-recipe.md` — step-by-step to add an MVP-B product.
- `docs/product-specs/mvp-b-handoff-note.md` — DoD handoff note for the team starting `ANY-32`/B01.
- Link both new docs from `docs/architecture/platform-boundaries.md` and
  `docs/product-specs/index.md`.
- Mark `A22c`/`ANY-25` `Done` in `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`.

### Out of scope

- Implementing any MVP-B product (`ANY-32`/B01 and later) — explicit ticket non-goal.
- `CLAUDE.md` vs `AGENTS.md` drift — pre-existing, untracked, unrelated to this ticket's repo
  impact list (`tests/architecture`, `docs/product-specs`, `docs/architecture/platform-boundaries.md`).

## Relevant docs

- `docs/architecture/platform-boundaries.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `plans/ANY-25.md` (issue + implementation plan + code review findings)

## Contracts touched

- None (test-only + docs; no runtime contract changes).

## Implementation steps

- [x] `tests/architecture/test_no_product_specific_endpoints.py` — AST-scans router files' route
      decorators, `APIRouter(prefix=...)`, and `include_router(..., prefix=...)` calls for
      hardcoded Freelancer product path terms.
- [x] `tests/architecture/test_litellm_model_strings_stay_in_provider_config.py` — scans
      `apps/`/`packages/`/`extensions/` source (excluding tests) for `model: <provider>/<model>`
      literals outside the two allowed provider-config files.
- [x] `docs/product-specs/add-product-recipe.md` — 8-step recipe anchored to the real
      `FreelancerSuiteBundle` example.
- [x] `docs/product-specs/mvp-b-handoff-note.md` — what's proven / allowed / forbidden, with the
      `kernel_demo` exception called out explicitly.
- [x] Linked both docs from `platform-boundaries.md` and `docs/product-specs/index.md`.
- [x] Marked `A22c`/`ANY-25` `Done` in `mvp-a-mvp-b-linear-epics.md`.
- [x] Code review (2026-08-31, `plans/ANY-25.md` "code review high run #1") found 4 gaps, all
      fixed:
  - `test_no_product_specific_endpoints.py`'s AST scanner only recognized route-decorator and bare
    `APIRouter(...)` calls, missing `app.include_router(router, prefix="/proposal_ai")` — the more
    likely real-world path for a product-specific prefix to land in `main.py`. Fixed: scanner now
    also inspects `include_router(...)`'s `prefix=` keyword. Verified with a synthetic
    `include_router(router, prefix="/proposal_ai")` file that the literal is now captured.
  - No exec plan existed under `docs/exec-plans/active/` for this ticket, per CLAUDE.md's "before
    coding" requirement. Fixed: this file.
  - `test_litellm_model_strings_stay_in_provider_config.py`'s `SKIP_PATH_PARTS` diverged from the
    neighboring `test_no_direct_provider_calls_outside_gateway.py`'s set (missing `.git`, `.tmp`,
    `tmp`, `uv-cache`). Fixed: added `.git`, `.tmp`, `tmp`, `uv-cache`. The claim that this made the
    two tests "walk the same tree" was itself wrong and got caught in code-review round 2: they
    scan fundamentally different roots (this test: `apps`/`packages`/`extensions` only, production
    source; the neighbor: the whole repo via `ROOT.rglob`) and this test deliberately keeps
    `"tests"` in its skip set (the neighbor skips `tests/` per-function instead, not via this
    constant) so real config values asserted in test fixtures don't false-positive. Fixed:
    corrected the comment to state the actual relationship (best-effort alignment on infra-noise
    entries, not identical trees) and closed the one remaining real gap (`uv-cache` without the
    leading dot, still missing after the round-1 fix). Round 3 fixed the drift properly:
    `test_litellm_model_strings_stay_in_provider_config.py` now imports
    `SKIP_PATH_PARTS` directly from `test_no_direct_provider_calls_outside_gateway` (`| {"tests"}`
    for its one intentional extra exclusion) instead of hand-maintaining a copy, so it structurally
    cannot drift from the neighbor again.
  - `ROUTERS_DIR.glob("*.py")` in `test_no_product_specific_endpoints.py` was non-recursive, so
    routers moved into a subpackage would silently drop out of coverage. Fixed: `rglob("*.py")`.
  - `LITELLM_MODEL_STRING_RE` matched any `<provider>/<word>` substring, so a comment like
    `# see https://github.com/openai/openai-python` false-positived. Fixed: anchored the pattern to
    a `model`-key context (`model[:=]"..."`/`model: ...`) so only an actual model-field value
    matches. Verified against both the false-positive comment (no match) and real
    YAML/Python/JSON-style `model:`/`model=`/`"model":` assignments (match). Round 3 found this
    anchor itself was too narrow (missed `DEFAULT_MODEL = "..."`, typed `self.default_model: str =
    "..."`); widened to match any identifier containing `model` (case-insensitive), an optional
    type annotation, and `:`/`=`/`==` before the value.
- [x] Code review round 2 (2026-08-31) found the round-1 `SKIP_PATH_PARTS` fix's own comment
      overclaimed ("walk the same tree" when the two tests scan structurally different roots);
      fixed by correcting the comment and adding the missing `uv-cache` entry (superseded by
      round 3's import-based fix above, which removes the duplicated constant entirely).
- [x] Code review round 3 (2026-08-31, `plans/ANY-25.md` "code review high run #3") found 3 more
      gaps beyond the `SKIP_PATH_PARTS` fix described above, all fixed:
  - `test_no_product_specific_endpoints.py`'s route-registration detector matched any
    `.get`/`.post`/etc. call, not just calls on a router — `request.query_params.get("view",
    "task-finder-debug")` inside a handler body would false-positive-fail the test on
    already-correct, `{product_id}`-parameterized code. Fixed: added `_router_variable_names`
    (finds `<name> = APIRouter(...)` bindings per module) and require the `.get`/etc. call's
    receiver to be one of those names. Verified with a synthetic file reproducing the exact
    false-positive (no longer flagged) alongside a genuine `@router.get("/proposal_ai/status")`
    case (still flagged) and the round-1 `include_router(prefix=...)` case (still flagged).
  - `docs/product-specs/add-product-recipe.md` step 6 pointed to
    `test_no_product_specific_endpoints.py` as boundary protection without noting that its
    `FORBIDDEN_PRODUCT_PATH_TERMS` is a static list of the 8 known Freelancer products — a 9th,
    genuinely new product's hardcoded path would not be caught. Fixed: added an explicit
    instruction in the recipe (and a matching note in the handoff note's enforcement section) to
    add the new product's name to that list when registering the bundle.
  - `ALLOWED_FILES` in `test_litellm_model_strings_stay_in_provider_config.py` excluded
    `configs/kernel/provider_policies.yaml`/`litellm_router.yaml`, but `SCAN_ROOTS` never included
    `configs/` at all, so the exclusion was dead code and nothing under `configs/` was ever
    scanned. Fixed: added `ROOT / "configs"` to `SCAN_ROOTS`; confirmed no other `configs/*.yaml`
    file trips the (now-reachable) regex.

## Validation

- [x] `python3 -m pytest tests/architecture -q` — 24 passed before the review fixes, still 24 after
      both review rounds.
- [x] `python3 scripts/agent/validate_architecture.py` — passed.
- [x] `python3 scripts/agent/runner.py validate-docs` — passed.
- [x] `python3 scripts/agent/runner.py quick-check` — 980 passed pre-fix, 981 passed post-round-1.
- [x] Manual check: synthetic `include_router(router, prefix="/proposal_ai")` file confirmed caught
      by the updated scanner.
- [x] Manual check: `LITELLM_MODEL_STRING_RE` confirmed it no longer matches the GitHub-URL comment
      false positive and still matches real `model:`/`model=`/`"model":` litellm-format values.
- [x] `python3 -m pytest tests/architecture -q` re-run after round-2 fix (corrected `SKIP_PATH_PARTS`
      comment, added `uv-cache`) — 24 passed.
- [x] Manual check: synthetic `request.query_params.get("view", "task-finder-debug")` inside a
      correctly `{product_id}`-parameterized handler no longer flagged after the round-3 router-
      receiver fix; a genuine `@router.get("/proposal_ai/status")` and the round-1
      `include_router(prefix=...)` case are both still flagged.
- [x] Manual check: widened `LITELLM_MODEL_STRING_RE` matches `DEFAULT_MODEL = "openai/..."`,
      `self.default_model: str = "openai/..."`, `"model": "openai/..."`, and `model: openai/...`;
      still does not match the GitHub-URL comment false positive.
- [x] `python3 -m pytest tests/architecture -q` and standalone
      `python3 -m pytest tests/architecture/test_litellm_model_strings_stay_in_provider_config.py -q`
      (confirms the cross-module `SKIP_PATH_PARTS` import resolves when that file runs alone) —
      both green after round 3.
- [x] `python3 scripts/agent/runner.py quick-check` re-run after round 3 — 981 passed.
- [x] `python3 scripts/agent/runner.py validate-docs` re-run after the recipe/handoff-note edits —
      passed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-31 | "No product-specific endpoints" test asserts against a forbidden-term list on known router files' route/prefix literals, not a general "every path is `{product_id}`-parameterized" proof. | FastAPI routes can be parameterized several ways; a general proof is brittle and over-engineered for 7 router files. Matches the existing forbidden-term-list style already used by `test_no_freelancer_terms_in_platform_core.py`. |
| 2026-08-31 | LiteLLM-model-string test scans production source only (`apps/`, `packages/`, `extensions/`, excluding `tests/`), not test fixtures. | Tests legitimately assert against the real config values (e.g. `test_litellm_adapter.py` asserting `response.model == "openai/gpt-4.1-mini"`); flagging those would be a false positive, not a real boundary violation. |
| 2026-08-31 | `demo.py`'s hardcoded `product_id="kernel_demo"` stays an explicit, documented exception rather than being folded into the forbidden-term check. | `kernel_demo` is the platform's own MVP-A1/A2 smoke product, not a Freelancer product — flagging it would break a legitimate, already-shipped router for no boundary benefit. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-31 | Implemented per `plans/ANY-25.md`: two new architecture tests, add-product recipe, MVP-B handoff note, doc links, tracker row. `quick-check` green (980 passed). | Await/act on code review. |
| 2026-08-31 | Code review round 1 found 4 gaps (missed `include_router(prefix=...)` path, missing exec plan, `SKIP_PATH_PARTS` drift between the two boundary tests, non-recursive router glob, regex false-positive on URL/comment text). Fixed all four, re-verified with targeted manual checks plus `pytest tests/architecture` and `quick-check` (981 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 2 found the round-1 `SKIP_PATH_PARTS` fix's own comment overclaimed ("walk the same tree") — the two tests scan structurally different roots regardless of the skip set, and `uv-cache` (no dot) was still missing after round 1. Fixed: corrected the comment to state the real relationship, added the missing entry. `pytest tests/architecture` green (24 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 3 found 3 more gaps: route-registration detector matched any object's `.get()`/etc. (false-positive on `request.query_params.get("view", "task-finder-debug")`), the model-string regex missed `ALL_CAPS`/typed-assignment forms, and the add-product recipe didn't say to extend the forbidden-term list for a new product (plus `ALLOWED_FILES` being dead code since `configs/` wasn't scanned). Fixed all: router-receiver check via `_router_variable_names`, widened regex, recipe/handoff-note note added, `configs/` added to `SCAN_ROOTS`, and replaced the hand-maintained `SKIP_PATH_PARTS` copy with a direct import from the neighbor test (removes the drift risk structurally instead of re-syncing by hand a third time). `pytest tests/architecture` (24 passed) and `quick-check` (981 passed) green. | Commit. |

## Open questions

- None.

## Follow-up debt

- None.
