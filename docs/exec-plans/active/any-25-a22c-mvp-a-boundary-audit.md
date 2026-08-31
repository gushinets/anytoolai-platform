# Execution Plan: ANY-25 A22c MVP-A Boundary Audit

## Status

- State: active
- Owner: agent
- Created: 2026-08-31
- Last updated: 2026-08-31
- Review date: 2026-08-31
- Next action: none — implementation, three internal code-review rounds, and eight GitHub PR
  review rounds of fixes landed; move to `completed/` once merged.
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
- [x] Repeat GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #2)", reviewing commit
      `0a3d7cb`) found 2 more gaps in the round-4/5 fixes themselves, both fixed:
  - The `api_route`/`add_api_route` fix from the previous round only widened
    `ROUTE_REGISTRATION_METHODS`; it didn't touch `_router_variable_names`, which still tracked only
    `<name> = APIRouter(...)` bindings. `main.py` binds `app = FastAPI(...)`, not `APIRouter(...)`,
    so `app.add_api_route("/proposal_ai/status", handler)` and
    `@app.api_route("/proposal_ai/status", methods=["GET"])` — a direct way to register a
    product-specific endpoint straight on the app — still bypassed the guard entirely. Fixed:
    `_router_variable_names` (renamed intent unchanged, still tracks the "route target" variable
    set) now also recognizes `<name> = FastAPI(...)` bindings via a shared
    `ROUTE_TARGET_CONSTRUCTORS = {"APIRouter", "FastAPI"}`. Verified both direct-`app` bypass cases
    (decorator and `add_api_route` call) are now caught.
  - `_strip_comment` found the first `#`/`//` anywhere on the line, including inside a quoted
    string — now that `.json` is scanned, a line like `{"callback": "https://example.com", "model":
    "openai/gpt-4.1"}` got truncated at the `//` in the URL, silently hiding the real `model` field
    that comes after it. The same shape breaks in Python/TS whenever a URL string precedes a
    hardcoded model literal on one line. Fixed: rewrote `_strip_comment` to track quote state
    (single/double, with backslash-escape handling) and only treat `#`/`//` as a comment start when
    not inside a string. Verified against the exact JSON-with-URL case from the review (now caught),
    plus every prior true/false-positive case (comment-only lines, `DEFAULT_MODEL = "..." #
    trailing comment`, a `#` inside a quoted string that isn't a comment).
- [x] Third GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #3)", reviewing commit
      `a558d76`) found 2 more gaps in the round-6 fixes themselves, both fixed:
  - The `FastAPI(...)`-binding fix only handled `ast.Assign` (`app = FastAPI()`). A type-annotated
    binding — `app: FastAPI = FastAPI()` or `router: APIRouter = APIRouter()`, ordinary valid
    Python — is a distinct `ast.AnnAssign` node with a singular `.target` instead of `.targets`, so
    it was never added to `router_names`; a hardcoded product path registered on an annotated
    `app`/`router` still passed the guard. Fixed: `_router_variable_names` now also matches
    `ast.AnnAssign` (extracted the shared "is this an `APIRouter`/`FastAPI` call" check into
    `_is_route_target_call` so both branches can't drift). Verified both an annotated
    `app.add_api_route(...)` and an annotated `@router.get(...)` are now caught.
  - The LiteLLM test's `SCAN_EXTS` covers `.js`/`.jsx`/`.ts`/`.tsx`, but neither the model regex nor
    `_strip_comment` treated backtick (`` ` ``) as a string delimiter — a JS/TS template literal
    like `` const model = `openai/gpt-4.1`; `` was invisible (the regex only accepted `'`/`"`/`=`/
    `:`/`,`/bracket/start-of-line immediately before the literal, and a backtick isn't in that set),
    and `` const url = `https://example.com`; const model = "openai/gpt-4.1"; `` was truncated at
    the URL's `//` because `_strip_comment` didn't know it was inside a backtick string. Fixed:
    added backtick to both the regex's allowed-prefix class and `_strip_comment`'s recognized quote
    characters. Verified both exact cases from the review are now caught, and the GitHub-URL
    comment false positive from earlier rounds is still excluded.
- [x] Fourth GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #4)", reviewing commit
      `87814fd`) found 2 more gaps, both fixed:
  - `_path_argument` only accepted an `ast.Constant`, so a route path factored into a module-level
    string constant (`PROPOSAL_STATUS_PATH = "/proposal_ai/status"` then
    `@router.get(PROPOSAL_STATUS_PATH)` or `router.add_api_route(PROPOSAL_STATUS_PATH, handler)`) —
    ordinary, common Python style — was invisible: the argument is an `ast.Name`, and
    `_path_argument` returned `None`. Fixed: added `_module_string_constants` (collects
    `<NAME> = "<literal>"` module-level bindings) and `_string_value` (resolves an `ast.Constant`
    directly or an `ast.Name` through that constants map); `_path_argument`/`_keyword_value` now
    both go through it, so the `prefix=` keyword on `APIRouter`/`include_router` gets the same
    resolution for free. Constant concatenation (`A + B`) was explicitly left unhandled — the
    review flagged it as "ideally", not blocking, and it's real added AST-walking complexity for a
    pattern not used anywhere in this repo's routers today. Verified with a synthetic
    `PROPOSAL_STATUS_PATH` constant referenced from both a decorator and `add_api_route`; both are
    now caught.
  - `_strip_comment` treated `//` as a comment marker for every scanned file type, but `//` is not
    a YAML/JSON comment marker — YAML allows a bare (unquoted) URL as a flow-mapping scalar, so a
    line like `settings: {callback: https://example.com, model: openai/gpt-4.1}` (valid YAML) got
    truncated at the URL's `//`, hiding the real `model` field. Fixed: comment markers are now
    looked up per file suffix via `_COMMENT_MARKERS_BY_SUFFIX` (`#` only for `.py`/`.yaml`/`.yml`,
    `#`+`//` for `.ts`/`.tsx`/`.js`/`.jsx`, none for `.json` since JSON has no comment syntax at
    all) instead of a single hardcoded set; `_strip_comment` takes the applicable markers as a
    parameter. Verified the exact YAML case from the review is now caught, real YAML/Python `#`
    comments are still stripped, and the round-2/round-3 JS/TS quoted-URL and backtick cases are
    unaffected.
- [x] Fifth GitHub PR review round (2026-08-31, inline comments on PR #96, no matching
      "Code-ewview" heading in `plans/ANY-25.md` this time) found 2 more gaps, both fixed:
  - `LITELLM_MODEL_STRING_RE`'s allowed-prefix class includes `=`, so a URL query value like
    `"https://example.com/callback?model=openai/gpt-4.1"` false-positived — the `=` right before
    `openai` reads identically to a real assignment. Fixed: added `_quoted_string_spans` (tracks
    each quoted string's content boundaries on the line, reusing the same quote-state approach as
    `_strip_comment`) and `_is_url_query_value` (true when a candidate match sits inside a quoted
    string that contains `://` before it); the test now iterates `finditer()` via a new
    `_first_real_offender` helper and skips any match `_is_url_query_value` rejects, instead of
    trusting the first `.search()` hit unconditionally. Verified the exact `?model=`/`&provider=`
    query-string cases from the review are now excluded, and every prior true-positive case (plain
    quoted/unquoted assignments, the round-8 YAML unquoted-URL-then-model case, JS/TS
    backtick/quoted-URL cases) still matches — the URL-query check only ever removes matches, never
    adds new ones, so it can't reintroduce an earlier false negative.
  - `_is_route_target_call` only recognized a bare-name constructor call (`FastAPI(...)`,
    `APIRouter(...)`); a module-qualified form (`import fastapi; app = fastapi.FastAPI()`) — the
    call's `func` is an `ast.Attribute`, not `ast.Name` — was invisible, so `app.add_api_route(...)`
    on a qualified-import-bound `app` still bypassed the guard. Fixed: `_is_route_target_call` now
    also accepts an `ast.Attribute` callee, checking `.attr` against `ROUTE_TARGET_CONSTRUCTORS` —
    the import alias (`fastapi`, `fa`, ...) is irrelevant since only the final attribute name is
    checked, so this covers any alias for free. Verified both `fastapi.FastAPI()` +
    `add_api_route(...)` and `fastapi.APIRouter()` + a decorator are now caught.
- [x] Sixth GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #5)", reviewing commit
      `bd321b6`) found 4 more gaps, all fixed:
  - `_module_string_constants` only handled `ast.Assign`, missing an annotated module constant
    (`PROPOSAL_STATUS_PATH: str = "/proposal_ai/status"`, an `ast.AnnAssign`) — invisible to
    `@router.get(PROPOSAL_STATUS_PATH)` the same way the un-annotated case was in round 8. Worse,
    it walked the *whole* tree (`ast.walk`), so a same-named local inside a function
    (`def helper(): PROPOSAL_STATUS_PATH = "/safe"`) could overwrite the real module-level value
    in the constants map, making a route resolve against the wrong string entirely. Fixed: scoped
    collection to `tree.body` (top-level statements only) and added the `AnnAssign` branch.
    Verified an annotated module constant now resolves, and a same-named nested local no longer
    shadows the real module-level value (route now correctly resolves to
    `/proposal_ai/status`, not the nested-local `/safe`).
  - `_is_route_target_call`'s bare-name branch only matched `FastAPI`/`APIRouter` literally, so
    `from fastapi import FastAPI as F; app = F()` (`func` is `ast.Name(id="F")`) still bypassed the
    guard despite the round-5 fix's comment/decision-log claiming aliases were handled — that fix
    only covered the *module-qualified* alias case (`fastapi.FastAPI()`, alias on the module), not
    an *imported* alias (`F` standing in for `FastAPI` itself). Fixed: added
    `_route_target_import_aliases` (maps `from fastapi import FastAPI as F` -> `{"F": "FastAPI"}`)
    and `_is_route_target_call` now also accepts a bare name that resolves through that map.
    Verified `from fastapi import FastAPI as F` + `F()` + `add_api_route(...)`, and the equivalent
    `APIRouter as R` + decorator case, are both now caught.
  - `_COMMENT_MARKERS_BY_SUFFIX` treated `#` as a JS/TS comment marker, but `#` is not JS/TS
    comment syntax — it's valid in modern private class fields (`class C { #cache = 1; ... }`), so
    a line like `class C { #cache = 1; static model = "openai/gpt-4.1"; }` got truncated at
    `#cache` before the real hardcode. Fixed: removed `#` from the `.ts`/`.tsx`/`.js`/`.jsx`
    entries, leaving only the genuine `//` marker (hashbang support left out per the review's own
    "if desired" hedge — no hashbang JS/TS files exist in this repo). Verified the exact private-
    field case is now caught, and real `//` comments are still stripped.
  - `_is_url_query_value` was broader than intended: it exempted *any* match inside a quoted
    string that contained `://` anywhere earlier, not just one that's actually part of a `?key=`/
    `&key=` query token — so a real hardcode sharing a quoted string with an unrelated URL (e.g.
    `payload = '{"callback":"https://example.com","model":"openai/gpt-4.1"}'`, a serialized-JSON
    blob) was wrongly suppressed. Fixed: added `_URL_QUERY_KEY_RE` and tightened the check to
    require the match's prefix char to literally be `=` *and* have a `?`/`&`-prefixed key
    immediately adjacent to it, not merely "some URL exists somewhere earlier in this string".
    Verified the serialized-JSON case is now caught while both round-9 URL-query false positives
    stay excluded.
- [x] Seventh GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #6)", reviewing commit
      `1fa87dd`) found 2 more gaps, both fixed:
  - The round-10 import-alias fix taught `_router_variable_names` to recognize an aliased
    constructor as a valid route-target receiver, but `_route_path_literals`'s separate
    `PREFIX_KEYWORD_CALLS` check (which extracts `APIRouter(prefix=...)`'s own prefix literal)
    still compared the raw `func_name` against the literal string `"APIRouter"` — so
    `from fastapi import APIRouter as R; router = R(prefix="/proposal_ai")` registered `router` as
    a recognized receiver (via the round-10 fix) but the prefix `"/proposal_ai"` itself was never
    collected as a literal, since `"R"` doesn't equal `"APIRouter"`. A subsequent
    `@router.get("/status")` then produced only `/status` as the checked literal, silently missing
    the forbidden `/proposal_ai` prefix entirely. Fixed: `_route_path_literals` now resolves
    `func_name` through the same `aliases` map (`aliases.get(func_name, func_name)`) before the
    `PREFIX_KEYWORD_CALLS` check, and both callers now share one `_route_target_import_aliases`
    computation instead of `_router_variable_names` computing its own. Verified
    `R(prefix="/proposal_ai")` + `@router.get("/status")` is now caught as `/proposal_ai`.
  - `_strip_comment` reset `in_string` to `None` at the start of every physical line (the function
    was called once per line, independently), so a `#`/`//` still lexically inside a multi-line
    string (a Python triple-quoted string, a JS/TS template literal) on a *continuation* line was
    misread as a real comment, truncating that line before a real hardcode that followed the
    string's close later on the same line. Fixed: replaced the per-line `_strip_comment` with
    `_strip_comments` (plural), which processes the whole file text once and carries `in_string`
    state across `\n` boundaries, returning the same list-of-stripped-lines shape the rest of the
    test already consumed (`_first_real_offender` now takes an already-stripped line instead of
    stripping it itself). Verified the exact triple-quoted-string case from the review is now
    caught, plus the analogous JS/TS multi-line template-literal case, and re-ran the full 16-case
    regression table from round 10 (now 18 cases) to confirm nothing else flipped.
- [x] Eighth GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #7)", reviewing commit
      `8b0b9d4`) found 2 more gaps, both fixed with a generalization rather than another one-off
      special case:
  - `called_on_router` only accepted a direct `ast.Name` receiver, so `app.router.add_api_route(
      "/proposal_ai/status", handler)` — valid, commonly-used FastAPI usage (`FastAPI.router` *is*
    the app's root `APIRouter`, a real public attribute) — was invisible, since the receiver
    (`app.router`) is an `ast.Attribute`, not a name in `router_names`. Rather than special-casing
    just `.router`, added `_is_router_expr`, a small recursive check: a name is a router expr if
    it's in `router_names`; an attribute access is a router expr if its own attribute is `router`
    and its value is itself a router expr. This covers `app.router` (and, for free, any deeper
    `x.router.router`-shaped chain, at no extra cost) instead of only the exact case the review
    named. Verified `app.router.add_api_route(...)` is now caught, and ordinary `router.get(...)`/
    `app.add_api_route(...)` registrations are unaffected.
  - `_strip_comments`'/`_quoted_string_spans`' shared `_QUOTE_CHARS` tracking treated `'`/`"`/`` ` ``
    each as independent 1-char delimiters, so a Python triple-quoted string (`"""..."""`) was
    misread as: open on the first `"`, close on the second, then treat the third `"` (and
    everything after) as ordinary code — so an interior single `"` inside the triple-quoted body
    (`"""first " quote\n..."""`) closed tracking early, leaving the next physical line
    out-of-string and its leading `#` misread as a real comment. Fixed at the root rather than
    patching around this one shape: added `_TRIPLE_QUOTES = ('"""', "'''")` and check for a 3-char
    triple-quote delimiter (longest-match-first) before falling back to the existing 1-char check,
    so open/close tracking now correctly spans the whole triple-quoted body regardless of interior
    single/double quotes. Verified the exact interior-quote case from the review is now caught,
    plus a control case (an ordinary docstring containing `#` and the word "model" but no real
    hardcode correctly stays unflagged), and re-ran the full 18-case regression table (now 19
    cases, rounds 4–12) to confirm nothing else flipped.

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
- [x] Manual check: `@app.api_route("/proposal_ai/status", methods=["GET"])` and
      `app.add_api_route("/proposal_ai/status2", handler)` on a `FastAPI()`-bound `app` (matching
      `main.py`'s real binding shape) are both caught after the `_router_variable_names`/
      `ROUTE_TARGET_CONSTRUCTORS` fix.
- [x] Manual check: `{"callback": "https://example.com", "model": "openai/gpt-4.1"}` is now caught
      (previously the naive `//`-anywhere comment stripper truncated the line at the URL, hiding the
      `model` field); re-verified every prior `_strip_comment` true/false-positive case still behaves
      correctly (comment-only lines, trailing `# comment` after a real assignment, a `#` that's
      inside a quoted string and isn't a comment).
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `app: FastAPI = FastAPI()` + `app.add_api_route("/proposal_ai/status", handler)`
      and `router: APIRouter = APIRouter()` + `@router.get("/proposal_ai/status")` (both annotated
      bindings) are caught after the `ast.AnnAssign` fix.
- [x] Manual check: `` const model = `openai/gpt-4.1`; `` and
      `` const url = `https://example.com`; const model = "openai/gpt-4.1"; `` are both caught
      after the backtick fix; the `# see https://github.com/...` comment false positive from
      earlier rounds is still excluded.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `PROPOSAL_STATUS_PATH = "/proposal_ai/status"` referenced from
      `@router.get(PROPOSAL_STATUS_PATH)` and from `router.add_api_route(PROPOSAL_STATUS_PATH,
      handler)` are both caught after the `_module_string_constants`/`_string_value` fix.
- [x] Manual check: `settings: {callback: https://example.com, model: openai/gpt-4.1}` (valid,
      unquoted-URL YAML) is caught after the per-suffix comment-marker fix; a real YAML `#` comment
      and a real JS/TS `// ...` comment are both still stripped; the round-2/round-3 JS/TS
      quoted-URL and backtick cases are unaffected.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `"https://example.com/callback?model=openai/gpt-4.1"` and
      `"https://example.com/hook?provider=openai/gpt-4.1&foo=1"` are both excluded after the
      URL-query fix; every prior true-positive case (quoted/unquoted assignments, the round-8
      YAML unquoted-URL-then-model case, JS/TS backtick/quoted-URL cases, `xai/grok-4`) still
      matches — ran the full 14-case regression table covering rounds 4–9 together to confirm no
      case flipped.
- [x] Manual check: `import fastapi; app = fastapi.FastAPI()` + `app.add_api_route(...)` and
      `import fastapi; router = fastapi.APIRouter()` + `@router.get(...)` are both caught after the
      `ast.Attribute` fix in `_is_route_target_call`.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: annotated module constant (`PROPOSAL_STATUS_PATH: str = "..."`) resolves, and
      a same-named nested-function local no longer shadows the real module-level value — the route
      correctly resolves to `/proposal_ai/status`, not the nested local's `/safe`.
- [x] Manual check: `from fastapi import FastAPI as F` + `F()` + `add_api_route(...)`, and
      `from fastapi import APIRouter as R` + `R()` + a decorator, are both caught after the
      `_route_target_import_aliases` fix.
- [x] Manual check: `class C { #cache = 1; static model = "openai/gpt-4.1"; }` is caught after
      removing `#` from the JS/TS comment-marker set; real `// ...` comments still stripped.
- [x] Manual check: `payload = '{"callback":"https://example.com","model":"openai/gpt-4.1"}'`
      (serialized JSON in a single-quoted string) is caught after tightening
      `_is_url_query_value`; the two round-9 URL-query false positives stay excluded. Re-ran the
      full regression table (now 16 cases, rounds 4–10) to confirm nothing else flipped.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `from fastapi import APIRouter as R; router = R(prefix="/proposal_ai")` +
      `@router.get("/status")` now yields `/proposal_ai` as a checked literal (previously only
      `/status` was collected).
- [x] Manual check: a Python triple-quoted string containing a bare `#` on a continuation line,
      with a real `MODEL = "openai/..."` hardcode later on that same (closing) line, is now
      caught; the analogous JS/TS multi-line template-literal case (containing `//`) is also
      caught. Re-ran the full 18-case regression table (rounds 4–11) to confirm nothing else
      flipped.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `app.router.add_api_route("/proposal_ai/status", handler)` on a
      `FastAPI()`-bound `app` is now caught via `_is_router_expr`; ordinary `router.get(...)` and
      `app.add_api_route(...)` registrations are unaffected.
- [x] Manual check: a triple-quoted string with an interior single `"` before a real trailing
      `#`-then-hardcode line (the exact review case) is now caught; a control case — an ordinary
      docstring containing `#` and the word "model" but no real provider/model hardcode — correctly
      stays unflagged. Re-ran the full 18-case regression table (now 19 cases, rounds 4–12) to
      confirm nothing else flipped.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-31 | "No product-specific endpoints" test asserts against a forbidden-term list on known router files' route/prefix literals, not a general "every path is `{product_id}`-parameterized" proof. | FastAPI routes can be parameterized several ways; a general proof is brittle and over-engineered for 7 router files. Matches the existing forbidden-term-list style already used by `test_no_freelancer_terms_in_platform_core.py`. |
| 2026-08-31 | LiteLLM-model-string test scans production source only (`apps/`, `packages/`, `extensions/`, `configs/`, excluding `tests/`), not test fixtures. | Tests legitimately assert against the real config values (e.g. `test_litellm_adapter.py` asserting `response.model == "openai/gpt-4.1-mini"`); flagging those would be a false positive, not a real boundary violation. |
| 2026-08-31 | `demo.py`'s hardcoded `product_id="kernel_demo"` stays an explicit, documented exception rather than being folded into the forbidden-term check. | `kernel_demo` is the platform's own MVP-A1/A2 smoke product, not a Freelancer product — flagging it would break a legitimate, already-shipped router for no boundary benefit. |
| 2026-08-31 | `LITELLM_PROVIDERS` is a hardcoded snapshot of `litellm`'s `provider_list`, not a runtime import of `litellm` itself. | `import litellm` anywhere outside the Provider Gateway/adapter layer violates this repo's own boundary (`docs/architecture/llm-runtime.md`); even the dedicated adapter test (`test_litellm_adapter.py`) imports only this repo's `providers.adapters.litellm` module, never raw `litellm` — no precedent for a raw import in tests either. A fully generic `<word>/<word>` pattern was rejected instead of a provider list at all: it matched this repo's own legitimate config-root strings (e.g. `"products/proposal_ai"` in `FreelancerSuiteBundle.config_roots()`). |
| 2026-08-31 | `test_no_product_specific_endpoints.py` tracks both `APIRouter(...)`- and `FastAPI(...)`-bound variable names as valid route-registration receivers, not just `APIRouter`. | `main.py`'s real binding is `app = FastAPI(...)`; routes can be (and, per the PR review, are a realistic path to be) registered directly on `app` via `add_api_route`/`api_route`, not only via a `router` object — the guard has to cover both binding shapes to actually enforce the boundary it claims to. |
| 2026-08-31 | `_router_variable_names` treats `ast.Assign` and `ast.AnnAssign` route-target bindings through one shared `_is_route_target_call` check rather than two separate ad hoc conditions. | The AnnAssign gap (round-3 PR review) existed because the Assign-only check was written once and never revisited when AnnAssign was later considered; sharing the "is this an `APIRouter`/`FastAPI` call" predicate removes the class of bug where one binding form's handling drifts from the other's. |
| 2026-08-31 | Backtick (`` ` ``) is a recognized string delimiter in both `LITELLM_MODEL_STRING_RE`'s prefix class and `_strip_comment`, alongside `'`/`"`. | `SCAN_EXTS` already covers `.js`/`.jsx`/`.ts`/`.tsx`; JS/TS template literals are ordinary syntax in those files, and treating only `'`/`"` as strings left both a detection gap (a backtick-quoted model literal never matched) and a truncation bug (a backtick-quoted URL's `//` was misread as a comment start). |
| 2026-08-31 | `_path_argument`/`_keyword_value` resolve a single module-level string constant reference, but not constant concatenation (`A + B`) or any other expression form. | The PR review flagged concatenation as "ideally" handled, not blocking; no router in this repo builds a path via constant concatenation today, and generalizing further (binary-op folding, f-strings, imported constants) is real added AST-walking complexity for a pattern that doesn't exist yet — YAGNI until it does. |
| 2026-08-31 | `_strip_comment`'s comment markers are looked up per file suffix (`_COMMENT_MARKERS_BY_SUFFIX`) instead of a single hardcoded `("#", "//")` tuple. | `//` is a JS/TS-only comment marker; treating it as universal truncated valid YAML (which allows a bare/unquoted URL scalar) and would have silently truncated valid JSON too (which has no comments at all) had a URL ever appeared there before the real hardcoded value. |
| 2026-08-31 | A candidate `LITELLM_MODEL_STRING_RE` match is rejected if it sits inside a quoted string that contains `://` before it (`_is_url_query_value`), rather than trusting the first regex match unconditionally. | A `?model=`/`&provider=` query parameter inside a URL string reads identically to a real assignment to the regex (both have `=` immediately before the provider name); the "inside a URL" check is scoped to the enclosing quoted string only, so it can't suppress a real hardcode that happens to share a line with an unrelated URL (confirmed against the round-8 YAML unquoted-URL-then-model case, which has no enclosing quote around the model field at all). Round 6/"Code-ewview (me #5)" found this was still too broad — "contains `://` before it" alone doesn't confirm the match is *part of* a URL query; tightened to also require the match's prefix char be `=` and a `?`/`&`-prefixed key sit immediately before it (`_URL_QUERY_KEY_RE`), so a real hardcode sharing a quoted string with an unrelated URL (a serialized-JSON blob) is no longer suppressed. |
| 2026-08-31 | `_module_string_constants` only collects `tree.body` (top-level statements), not the whole tree via `ast.walk`. | Walking the whole tree would let a same-named local inside a function/class shadow the real module-level constant in the resulting dict — a route referencing the module constant would then silently resolve against whatever that unrelated local happened to be, which is worse than not resolving it at all. |
| 2026-08-31 | `_is_route_target_call` accepts both a bare-name (`FastAPI(...)`) and a module-qualified (`fastapi.FastAPI(...)`) constructor call, checking only the final attribute/name against `ROUTE_TARGET_CONSTRUCTORS`. | The *module* alias (`fastapi`, `fa`, ...) is irrelevant to the qualified form; checking only the terminal attribute covers every module alias without needing to track the `import` statement itself. This entry originally also claimed an *imported* rebind (`from fastapi import FastAPI as F`) was covered — that was wrong (caught by round 6/"Code-ewview (me #5)"): the bare-name branch only ever matched the literal string `"FastAPI"`, so `F()` was invisible until `_route_target_import_aliases` was added (see the entry below). Corrected here rather than left standing, per the round-2 lesson about not letting an inaccurate self-report mislead a future reader. |
| 2026-08-31 | `_route_target_import_aliases` maps a local import name to the real constructor name (`from fastapi import FastAPI as F` -> `{"F": "FastAPI"}`) by reading `ast.ImportFrom` nodes, rather than trying to infer aliasing from the call site alone. | The call site (`F()`) carries no information about what `F` originally was — only the `import` statement does; a dedicated alias map is the only way to resolve a rebound name, and it's cheap (one pass over `ImportFrom` nodes) compared to full symbol-table resolution. |
| 2026-08-31 | `_COMMENT_MARKERS_BY_SUFFIX` treats JS/TS comment stripping as `("//",)` only, not `("#", "//")`. | `#` was never valid JS/TS comment syntax to begin with (it's real syntax for private class fields since ES2022) — carrying it over from the Python/YAML entry in round 4 was a straight copy error, not a deliberate tradeoff; it had no upside and one confirmed false-negative failure mode. |
| 2026-08-31 | `_route_path_literals` and `_router_variable_names` share one `_route_target_import_aliases(tree)` computation (computed once in `_route_path_literals`, passed into `_router_variable_names`) rather than each resolving aliases independently. | The round-11 `APIRouter as R` prefix-extraction gap existed specifically because the alias map was only wired into one of the two places that needed it (`_router_variable_names`'s receiver check) and not the other (`_route_path_literals`'s `PREFIX_KEYWORD_CALLS` check); sharing one computation makes it structurally harder for a future alias-aware feature to only wire in half the call sites. |
| 2026-08-31 | `_strip_comments` (plural) processes a file's entire text in one pass, carrying `in_string` state across `\n` boundaries, rather than calling a per-line `_strip_comment` independently for each line. | Python triple-quoted strings and JS/TS template literals are ordinary multi-line syntax in the file types this test scans; resetting quote state at every newline is only correct for single-line strings, and the round-11 review showed the gap is real (a `#`/`//` inside a still-open multi-line string was misread as a comment, truncating a real hardcode later on the string's closing line). |
| 2026-08-31 | `_is_router_expr` is a small recursive check (a name in `router_names`, or a `.router` attribute access on another router expr) rather than special-casing `app.router.add_api_route(...)` as one more literal pattern. | Every round so far that special-cased one exact call shape got caught missing a sibling shape next round (aliases, annotated bindings, qualified access, now `.router`); a recursive structural check closes the whole "any chain of router-valued expressions" class in one place instead of adding another parallel branch that the *next* review round finds a gap next to. |
| 2026-08-31 | `_TRIPLE_QUOTES` (`"""`/`'''`) is checked as an atomic 3-char delimiter before falling back to the existing 1-char `_QUOTE_CHARS` check, rather than teaching the 1-char tracker to special-case an interior quote. | Treating `"""` as three independent 1-char delimiters is categorically wrong for Python triple-quoted strings (closes after the first char, reopens on the second, and any interior single/double quote inside the body then desyncs tracking for the rest of the file) — this isn't a narrower version of the existing bug, it needed the delimiter itself modeled correctly. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-31 | Implemented per `plans/ANY-25.md`: two new architecture tests, add-product recipe, MVP-B handoff note, doc links, tracker row. `quick-check` green (980 passed). | Await/act on code review. |
| 2026-08-31 | Code review round 1 found 5 gaps (missed `include_router(prefix=...)` path, missing exec plan, `SKIP_PATH_PARTS` drift between the two boundary tests, non-recursive router glob, regex false-positive on URL/comment text). Fixed all five, re-verified with targeted manual checks plus `pytest tests/architecture` and `quick-check` (981 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 2 found the round-1 `SKIP_PATH_PARTS` fix's own comment overclaimed ("walk the same tree") — the two tests scan structurally different roots regardless of the skip set, and `uv-cache` (no dot) was still missing after round 1. Fixed: corrected the comment to state the real relationship, added the missing entry. `pytest tests/architecture` green (24 passed). | Await/act on next code review. |
| 2026-08-31 | Code review round 3 found 3 more gaps: route-registration detector matched any object's `.get()`/etc. (false-positive on `request.query_params.get("view", "task-finder-debug")`), the model-string regex missed `ALL_CAPS`/typed-assignment forms, and the add-product recipe didn't say to extend the forbidden-term list for a new product (plus `ALLOWED_FILES` being dead code since `configs/` wasn't scanned). Fixed all: router-receiver check via `_router_variable_names`, widened regex, recipe/handoff-note note added, `configs/` added to `SCAN_ROOTS`, and replaced the hand-maintained `SKIP_PATH_PARTS` copy with a direct import from the neighbor test (removes the drift risk structurally instead of re-syncing by hand a third time). `pytest tests/architecture` (24 passed) and `quick-check` (981 passed) green. | Await/act on next code review. |
| 2026-08-31 | GitHub PR #96 review round found 6 gaps: 2 stale-doc-text items in this file (gap counts, scan-root descriptions) plus `mvp-a-mvp-b-linear-epics.md`'s stale "Last updated", and 2 substantive test-logic gaps — `LITELLM_MODEL_STRING_RE` still keyed off a `model`-named identifier (missed `DEFAULT_LLM`/`deployment`-named hardcodes) and the endpoint test's route-literal collection grabbed every string arg, not just the path (false-positive risk from `summary=`/`description=` prose). Fixed all six: corrected the doc staleness, rewrote the model-string detector to key off literal position (preceded by quote/`=`/`:`/`,`/bracket/start-of-line) plus a comment stripper instead of the key name, and restricted route-literal collection to `_path_argument` (first positional arg or `path=` keyword). `pytest tests/architecture` (24 passed) and `quick-check` (981 passed) green. | Address the remaining 3 findings in the same PR-review comment block. |
| 2026-08-31 | Completed the same GitHub PR #96 review block's remaining 3 findings: `ROUTE_REGISTRATION_METHODS` missed `api_route`/`add_api_route` (and the remaining HTTP verbs) so those FastAPI registration styles bypassed the endpoint guard entirely; `SCAN_EXTS` omitted `.json` despite the regex already handling JSON syntax; the provider segment was a 9-name hand-written allowlist that missed any provider not on it (e.g. `xai`, `deepseek`). Fixed all three: expanded `ROUTE_REGISTRATION_METHODS`, added `.json` to `SCAN_EXTS`, and replaced the 9-name list with a 141-name static snapshot of `litellm`'s real `provider_list` (a fully generic pattern was tried first and rejected — it matched this repo's own `"products/proposal_ai"`-style config-root strings). `pytest tests/architecture` (24 passed), `validate-architecture`, and `quick-check` (981 passed) green. | Commit. |
| 2026-08-31 | Second GitHub PR #96 review round ("Code-ewview (me #2)", reviewing commit `0a3d7cb`) found the two prior fixes were each only partial: the `api_route`/`add_api_route` fix widened the method set but never taught `_router_variable_names` to recognize `app = FastAPI(...)` (only `APIRouter(...)`), so `app.add_api_route(...)`/`@app.api_route(...)` — the exact shape `main.py` actually uses — still bypassed the guard; and `_strip_comment` found `#`/`//` anywhere on the line including inside quoted strings, so a `.json` line with a URL before the `model` field (`{"callback": "https://...", "model": "openai/..."}`) got truncated before the real hardcode was ever inspected. Fixed both: `_router_variable_names` now also matches `FastAPI(...)` bindings via `ROUTE_TARGET_CONSTRUCTORS`, and `_strip_comment` is now quote-state-aware instead of a naive first-occurrence search. Verified both exact bypass cases from the review are now caught, all prior comment-stripping cases still behave correctly, and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Third GitHub PR #96 review round ("Code-ewview (me #3)", reviewing commit `a558d76`) found the `FastAPI(...)`-binding fix was itself only partial — it handled `ast.Assign` but not the distinct `ast.AnnAssign` node a type-annotated binding (`app: FastAPI = FastAPI()`, ordinary valid Python) parses to, so an annotated `app`/`router` still bypassed the guard — and that the LiteLLM test's model regex/`_strip_comment` never treated backtick as a string delimiter despite `SCAN_EXTS` covering `.js`/`.jsx`/`.ts`/`.tsx`, so a JS/TS template-literal model string was invisible and a backtick-quoted URL before a model literal on the same line got truncated the same way the round-2 quoted-URL bug did. Fixed both: extracted `_is_route_target_call` so `Assign`/`AnnAssign` share one check, and added backtick to the regex's prefix class and `_strip_comment`'s quote characters. Verified both exact cases from the review are now caught, and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Fourth GitHub PR #96 review round ("Code-ewview (me #4)", reviewing commit `87814fd`) found: `_path_argument` only accepted a literal `ast.Constant`, so a route path factored into a module-level string constant (`PROPOSAL_STATUS_PATH = "/proposal_ai/status"` then `@router.get(PROPOSAL_STATUS_PATH)`) — ordinary Python style — bypassed the guard entirely; and `_strip_comment` treated `//` as a comment marker universally, but `//` isn't a YAML/JSON comment marker, so a valid unquoted-URL YAML line (`settings: {callback: https://x, model: openai/y}`) got truncated before the real hardcode. Fixed both: added `_module_string_constants`/`_string_value` so a single-constant path/prefix reference resolves (constant concatenation explicitly left unhandled — flagged as "ideally", not blocking, and no router uses that pattern today); replaced the universal comment-marker tuple with `_COMMENT_MARKERS_BY_SUFFIX` so YAML/Python only strip `#`, JS/TS strip `#`+`//`, and JSON strips nothing. Verified both exact cases from the review are now caught, `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Fifth GitHub PR #96 review round (inline comments, reviewing commit `5045e81`) found: `LITELLM_MODEL_STRING_RE`'s prefix class includes `=`, so a `?model=`/`&provider=` query value inside a URL string false-positived the same as a real assignment; and `_is_route_target_call` only recognized a bare-name constructor call, so a module-qualified `fastapi.FastAPI(...)`/`fastapi.APIRouter(...)` binding still bypassed the endpoint guard. Fixed both: added `_quoted_string_spans`/`_is_url_query_value`/`_first_real_offender` so a candidate match inside a quoted string containing `://` before it is rejected (switched from `.search()` to `.finditer()` to allow skipping a rejected match and trying the next one on the same line); and `_is_route_target_call` now also accepts an `ast.Attribute` callee, checking only the final attribute name (alias-agnostic). Verified both exact cases from the review are now excluded/caught respectively, re-ran the full 14-case regression table spanning rounds 4–9 to confirm no prior case flipped, and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Sixth GitHub PR #96 review round ("Code-ewview (me #5)", reviewing commit `bd321b6`) found the round-5/round-9 fixes were each still incomplete, plus one clean new gap: (1) `_module_string_constants` missed annotated module constants and, more seriously, let a same-named nested-function local silently overwrite the real module-level value; (2) the round-5 alias fix only covered module-qualified access (`fastapi.FastAPI()`), not an *imported* rebind (`from fastapi import FastAPI as F`) despite the decision log claiming otherwise; (3) `_COMMENT_MARKERS_BY_SUFFIX` treated `#` as a JS/TS comment marker, which it never was (it's private-class-field syntax); (4) `_is_url_query_value` exempted any match sharing a quoted string with an earlier `://`, not just one that's actually a `?key=`/`&key=` token, so a serialized-JSON hardcode got wrongly suppressed. Fixed all four: scoped constant collection to `tree.body`; added `_route_target_import_aliases` to resolve imported rebinds; dropped `#` from the JS/TS marker set; tightened `_is_url_query_value` with `_URL_QUERY_KEY_RE`. Corrected the round-5 decision-log entry's overclaim rather than leaving it standing. Verified all four exact cases from the review, re-ran the full 16-case regression table spanning rounds 4–10 (nothing flipped), and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Seventh GitHub PR #96 review round ("Code-ewview (me #6)", reviewing commit `1fa87dd`) found the round-10 alias fix was itself only half-applied — it fixed the receiver check in `_router_variable_names` but not the separate `PREFIX_KEYWORD_CALLS` literal-string comparison in `_route_path_literals`, so `from fastapi import APIRouter as R; router = R(prefix="/proposal_ai")` still lost the `/proposal_ai` prefix entirely — plus a clean new gap: `_strip_comment` reset its quote-tracking state at every physical line, so a `#`/`//` still lexically inside a multi-line string (Python triple-quote, JS/TS template literal) on a continuation line was misread as a real comment, truncating a real hardcode later on that line. Fixed both: resolved `func_name` through the same alias map before the `PREFIX_KEYWORD_CALLS` check (and had `_route_path_literals`/`_router_variable_names` share one `_route_target_import_aliases` computation instead of each resolving independently); replaced the per-line `_strip_comment` with a whole-file, state-carrying `_strip_comments`. Verified both exact cases from the review, plus the analogous JS/TS multi-line case, re-ran the full 18-case regression table spanning rounds 4–11 (nothing flipped), and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Eighth GitHub PR #96 review round ("Code-ewview (me #7)", reviewing commit `8b0b9d4`) found `app.router.add_api_route(...)` — valid FastAPI usage via the app's public `.router` attribute — still bypassed the endpoint guard (receiver was an `ast.Attribute`, not a tracked `ast.Name`), and that the string-tracker's `_QUOTE_CHARS`-only model misreads Python triple-quoted strings as three independent 1-char delimiters, so an interior single `"` inside a triple-quoted body desynced tracking and let a following `#` on the next line be misread as a real comment. This time fixed both with a generalization instead of another one-off special case: `_is_router_expr` (a small recursive router/`.router`-chain check) replaces the direct-`ast.Name`-only receiver check; `_TRIPLE_QUOTES` is checked as an atomic 3-char delimiter before the 1-char fallback. Verified both exact cases from the review, a control case (an ordinary docstring with `#` and the word "model" but no real hardcode stays unflagged), re-ran the full 19-case regression table spanning rounds 4–12 (nothing flipped), and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Commit. |

## Open questions

- None.

## Follow-up debt

- None.
