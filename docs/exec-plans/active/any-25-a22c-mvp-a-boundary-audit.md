# Execution Plan: ANY-25 A22c MVP-A Boundary Audit

## Status

- State: active
- Owner: agent
- Created: 2026-08-31
- Last updated: 2026-08-31
- Review date: 2026-08-31
- Next action: none — implementation, three internal code-review rounds, and one GitHub PR review
  round of fixes landed; move to `completed/` once merged.
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
      `apps/`/`packages/`/`extensions/`/`configs/` source (excluding tests) for
      `<provider>/<model>` literals outside the two allowed provider-config files.
- [x] `docs/product-specs/add-product-recipe.md` — 8-step recipe anchored to the real
      `FreelancerSuiteBundle` example.
- [x] `docs/product-specs/mvp-b-handoff-note.md` — what's proven / allowed / forbidden, with the
      `kernel_demo` exception called out explicitly.
- [x] Linked both docs from `platform-boundaries.md` and `docs/product-specs/index.md`.
- [x] Marked `A22c`/`ANY-25` `Done` in `mvp-a-mvp-b-linear-epics.md`.
- [x] Code review (2026-08-31, `plans/ANY-25.md` "code review high run #1") found 5 gaps, all
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
- [x] GitHub PR review round (2026-08-31, PR #96, mirrored into `plans/ANY-25.md`) found 6 gaps,
      2 doc-staleness items fixed as minimal text edits and 4 more substantive, all fixed:
  - Doc staleness: this file's own "Next action" line still said "one round of code-review fixes"
    and the round-1 summary line said "found 4 gaps" against a 5-bullet list — both left over from
    editing this file incrementally across 3 review rounds. Fixed: "three rounds"/"found 5 gaps"
    (and the matching Progress-log entry, same stale count, fixed for the same reason).
  - This file's implementation-step and decision-log lines describing
    `test_litellm_model_strings_stay_in_provider_config.py`'s scan roots still said
    `apps/`/`packages/`/`extensions/` only, stale since round 3 added `configs/` to `SCAN_ROOTS`.
    Fixed both mentions; also updated the stale `model: <provider>/<model>` phrasing (superseded by
    the detection-logic fix below, which stopped requiring a `model`-named key at all).
  - `mvp-a-mvp-b-linear-epics.md`'s "Last updated" status line was still `2026-08-06` despite this
    ticket editing that file today. Fixed: `2026-08-31`.
  - `LITELLM_MODEL_STRING_RE` only matched a literal preceded by an identifier containing `model`
    — `DEFAULT_LLM = "openai/gpt-4o-mini"` or `deployment: "azure/my-deployment"` would bypass the
    check entirely regardless of key name. Fixed: detection no longer keys off the identifier name
    at all — it requires the `<provider>/<model>` literal to be immediately preceded by a
    quote/`=`/`:`/`,`/bracket/start-of-line (never true for a substring embedded in prose or a URL
    path, e.g. `github.com/openai/openai-python`'s `openai` is preceded by `/`), plus a
    `#`/`//` end-of-line comment stripper per line so a URL/reference living in a comment can't
    false-positive either. Verified against all round-1/round-3 true-positive cases, the two new
    named cases (`DEFAULT_LLM`, `deployment`), the GitHub-URL false positive in both `#` and `//`
    comment styles, and a full re-scan of the real `SCAN_ROOTS` tree (no new offenders).
  - `test_no_product_specific_endpoints.py`'s route-registration branch collected every string
    positional/keyword argument, not just the path — a `summary=`/`description=` kwarg containing a
    forbidden substring by coincidence would false-positive-fail an otherwise-correct,
    `{product_id}`-parameterized route. Fixed: added `_path_argument` (first positional arg, or the
    `path=` keyword) and collect only that. Verified with a synthetic
    `@router.post("/{product_id}/status", summary="task-finder debug helper")` (no longer flagged),
    a genuine `@router.get("/proposal_ai/status")` (still flagged), and `@router.get(path="/proposal_ai/status")`
    (still flagged via the keyword form).
- [x] Completing GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #1)" — this comment
      block held 5 findings total; 2 were fixed earlier as part of the "5 gaps" round above, these
      are the remaining 3), all fixed:
  - `test_no_product_specific_endpoints.py`'s `ROUTE_REGISTRATION_METHODS` only recognized
    `get`/`post`/`put`/`delete`/`patch` on a router — `@router.api_route("/proposal_ai/status",
    methods=["GET"])` and `router.add_api_route("/proposal_ai/status", handler)` bypassed the scan
    entirely. Fixed: added `api_route`, `add_api_route`, and the remaining HTTP verbs
    (`options`/`head`/`trace`) to the set. Verified both bypass cases are now caught (path
    extraction reuses the existing `_path_argument`/router-receiver logic unchanged).
  - `SCAN_EXTS` in `test_litellm_model_strings_stay_in_provider_config.py` omitted `.json`, even
    though the regex already matches JSON-style `"model": "..."` syntax — a `.json` config/fixture
    file was invisible to the guard. Fixed: added `.json`. Confirmed a real `"model":
    "openai/gpt-4.1"` JSON fixture is now caught, and a full re-scan of the real tree with `.json`
    included finds no new offenders.
  - The provider segment was a 9-name hand-written allowlist, so any valid LiteLLM provider not on
    it (e.g. `xai/grok-4`, `deepseek/deepseek-chat`) passed silently. A fully generic
    `<word>/<word>` pattern was tried and rejected: it matched this repo's own legitimate
    `"products/proposal_ai"`-style config-root path strings (e.g.
    `FreelancerSuiteBundle.config_roots()`), which is a worse failure mode than the narrow
    allowlist. Fixed: replaced the 9-name list with a 141-name static snapshot of
    `litellm==1.89.3`'s real `provider_list` (covers `xai`/`deepseek` and every other
    currently-known LiteLLM provider) — not imported at runtime, since importing `litellm` directly
    in a test would itself violate this repo's litellm-import boundary; the snapshot and its
    refresh command are documented in a `ponytail:` comment in the test file. Verified: `xai/grok-4`
    and `deepseek/deepseek-chat` are now caught; a full re-scan of the real `SCAN_ROOTS` tree with
    all 141 names finds zero false positives (checked names most likely to collide with real repo
    strings — `custom`, `github`, `pg_vector`, `milvus`, `sap`, `v0` — explicitly).

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
- [x] Manual check: widened `LITELLM_MODEL_STRING_RE` still matches every prior true-positive case
      plus `DEFAULT_LLM = "openai/..."` and `deployment: "azure/..."`; still does not match the
      GitHub-URL comment false positive in either `#` or `//` style.
- [x] `python3 -m pytest tests/architecture/test_litellm_model_strings_stay_in_provider_config.py -q`
      re-run after the round-4 detection-logic rewrite — passed, no new offenders found scanning the
      real `apps/`/`packages/`/`extensions/`/`configs/` tree.
- [x] Manual check: synthetic `@router.post("/{product_id}/status", summary="task-finder debug
      helper")` no longer flagged after the round-4 `_path_argument` fix; genuine
      `@router.get("/proposal_ai/status")` and `@router.get(path="/proposal_ai/status")` both still
      flagged.
- [x] `python3 -m pytest tests/architecture -q` re-run after round 4 — 24 passed.
- [x] `python3 scripts/agent/runner.py quick-check` re-run after round 4 — 981 passed.
- [x] Manual check: `@router.api_route("/proposal_ai/status", methods=["GET"])` and
      `router.add_api_route("/proposal_ai/status", handler)` both caught after the
      `ROUTE_REGISTRATION_METHODS` expansion.
- [x] Manual check: a `.json` fixture containing `{"model": "openai/gpt-4.1"}` is caught after
      adding `.json` to `SCAN_EXTS`.
- [x] Manual check: `model = "xai/grok-4"` and `model = "deepseek/deepseek-chat"` are both caught
      after the provider-list expansion; a full re-scan of the real `SCAN_ROOTS` tree (now including
      `.json`) with all 141 provider names finds zero false positives.
- [x] `python3 -m pytest tests/architecture -q` and `python3 scripts/agent/validate_architecture.py`
      re-run after completing the PR review round — both green.
- [x] `python3 scripts/agent/runner.py quick-check` re-run after completing the PR review round —
      981 passed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-31 | "No product-specific endpoints" test asserts against a forbidden-term list on known router files' route/prefix literals, not a general "every path is `{product_id}`-parameterized" proof. | FastAPI routes can be parameterized several ways; a general proof is brittle and over-engineered for 7 router files. Matches the existing forbidden-term-list style already used by `test_no_freelancer_terms_in_platform_core.py`. |
| 2026-08-31 | LiteLLM-model-string test scans production source only (`apps/`, `packages/`, `extensions/`, `configs/`, excluding `tests/`), not test fixtures. | Tests legitimately assert against the real config values (e.g. `test_litellm_adapter.py` asserting `response.model == "openai/gpt-4.1-mini"`); flagging those would be a false positive, not a real boundary violation. |
| 2026-08-31 | `demo.py`'s hardcoded `product_id="kernel_demo"` stays an explicit, documented exception rather than being folded into the forbidden-term check. | `kernel_demo` is the platform's own MVP-A1/A2 smoke product, not a Freelancer product — flagging it would break a legitimate, already-shipped router for no boundary benefit. |
| 2026-08-31 | `LITELLM_PROVIDERS` is a hardcoded snapshot of `litellm`'s `provider_list`, not a runtime import of `litellm` itself. | `import litellm` anywhere outside the Provider Gateway/adapter layer violates this repo's own boundary (`docs/architecture/llm-runtime.md`); even the dedicated adapter test (`test_litellm_adapter.py`) imports only this repo's `providers.adapters.litellm` module, never raw `litellm` — no precedent for a raw import in tests either. A fully generic `<word>/<word>` pattern was rejected instead of a provider list at all: it matched this repo's own legitimate config-root strings (e.g. `"products/proposal_ai"` in `FreelancerSuiteBundle.config_roots()`). |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-31 | Implemented per `plans/ANY-25.md`: two new architecture tests, add-product recipe, MVP-B handoff note, doc links, tracker row. `quick-check` green (980 passed). | Await/act on code review. |
| 2026-08-31 | Code review round 1 found 5 gaps (missed `include_router(prefix=...)` path, missing exec plan, `SKIP_PATH_PARTS` drift between the two boundary tests, non-recursive router glob, regex false-positive on URL/comment text). Fixed all five, re-verified with targeted manual checks plus `pytest tests/architecture` and `quick-check` (981 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 2 found the round-1 `SKIP_PATH_PARTS` fix's own comment overclaimed ("walk the same tree") — the two tests scan structurally different roots regardless of the skip set, and `uv-cache` (no dot) was still missing after round 1. Fixed: corrected the comment to state the real relationship, added the missing entry. `pytest tests/architecture` green (24 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 3 found 3 more gaps: route-registration detector matched any object's `.get()`/etc. (false-positive on `request.query_params.get("view", "task-finder-debug")`), the model-string regex missed `ALL_CAPS`/typed-assignment forms, and the add-product recipe didn't say to extend the forbidden-term list for a new product (plus `ALLOWED_FILES` being dead code since `configs/` wasn't scanned). Fixed all: router-receiver check via `_router_variable_names`, widened regex, recipe/handoff-note note added, `configs/` added to `SCAN_ROOTS`, and replaced the hand-maintained `SKIP_PATH_PARTS` copy with a direct import from the neighbor test (removes the drift risk structurally instead of re-syncing by hand a third time). `pytest tests/architecture` (24 passed) and `quick-check` (981 passed) green. | Await/act on next code review. |
| 2026-08-31 | GitHub PR #96 review round found 6 gaps: 2 stale-doc-text items in this file (gap counts, scan-root descriptions) plus `mvp-a-mvp-b-linear-epics.md`'s stale "Last updated", and 2 substantive test-logic gaps — `LITELLM_MODEL_STRING_RE` still keyed off a `model`-named identifier (missed `DEFAULT_LLM`/`deployment`-named hardcodes) and the endpoint test's route-literal collection grabbed every string arg, not just the path (false-positive risk from `summary=`/`description=` prose). Fixed all six: corrected the doc staleness, rewrote the model-string detector to key off literal position (preceded by quote/`=`/`:`/`,`/bracket/start-of-line) plus a comment stripper instead of the key name, and restricted route-literal collection to `_path_argument` (first positional arg or `path=` keyword). `pytest tests/architecture` (24 passed) and `quick-check` (981 passed) green. | Address the remaining 3 findings in the same PR-review comment block. |
| 2026-08-31 | Completed the same GitHub PR #96 review block's remaining 3 findings: `ROUTE_REGISTRATION_METHODS` missed `api_route`/`add_api_route` (and the remaining HTTP verbs) so those FastAPI registration styles bypassed the endpoint guard entirely; `SCAN_EXTS` omitted `.json` despite the regex already handling JSON syntax; the provider segment was a 9-name hand-written allowlist that missed any provider not on it (e.g. `xai`, `deepseek`). Fixed all three: expanded `ROUTE_REGISTRATION_METHODS`, added `.json` to `SCAN_EXTS`, and replaced the 9-name list with a 141-name static snapshot of `litellm`'s real `provider_list` (a fully generic pattern was tried first and rejected — it matched this repo's own `"products/proposal_ai"`-style config-root strings). `pytest tests/architecture` (24 passed), `validate-architecture`, and `quick-check` (981 passed) green. | Commit. |

## Open questions

- None.

## Follow-up debt

- None.
