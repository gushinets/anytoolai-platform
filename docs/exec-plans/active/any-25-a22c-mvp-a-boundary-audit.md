# Execution Plan: ANY-25 A22c MVP-A Boundary Audit

## Status

- State: active
- Owner: agent
- Created: 2026-08-31
- Last updated: 2026-08-31
- Review date: 2026-08-31
- Next action: none — implementation, three internal code-review rounds, and thirteen GitHub PR
  review rounds of fixes landed (round 10 replaced the hand-rolled Python/YAML lexer with real
  parsers; round 11 extended router-identity resolution to the whole package and fixed two gaps
  that rewrite itself exposed; round 12 fixed a `__init__.py` relative-import edge case in that
  same resolution and a JS/TS block-comment gap; round 13 added a second router-identity source
  for module-qualified imports and a JS/TS regex-literal heuristic — see those entries); move to
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
  - `_strip_comments`'s `_QUOTE_CHARS` tracking treated `'`/`"`/`` ` `` each as independent 1-char
    delimiters, so a Python triple-quoted string (`"""..."""`) was misread as: open on the first
    `"`, close on the second, then treat the third `"` (and everything after) as ordinary code —
    so an interior single `"` inside the triple-quoted body (`"""first " quote\n..."""`) closed
    tracking early, leaving the next physical line out-of-string and its leading `#` misread as a
    real comment. Fixed at the root rather than patching around this one shape: added
    `_TRIPLE_QUOTES = ('"""', "'''")` and check for a 3-char triple-quote delimiter
    (longest-match-first) before falling back to the existing 1-char check, so open/close tracking
    now correctly spans the whole triple-quoted body regardless of interior single/double quotes.
    Verified the exact interior-quote case from the review is now caught, plus a control case (an
    ordinary docstring containing `#` and the word "model" but no real hardcode correctly stays
    unflagged), and re-ran the full 18-case regression table (now 19 cases, rounds 4–12) to
    confirm nothing else flipped. **Correction (round 13):** the round-12 fix only touched
    `_strip_comments`; the sibling `_quoted_string_spans` helper (used by the URL-query exemption)
    kept the old 1-char-only tracker and had the identical bug — this line originally implied both
    were fixed together, which was inaccurate. See the round-13 entry below.
- [x] Ninth GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #8)", reviewing commit
      `0b4a469`) found 1 blocking coverage gap and 1 non-blocking correctness gap, both fixed:
  - **Blocking.** `test_no_product_specific_endpoints.py` only scanned `ROUTERS_DIR.rglob("*.py")`
    plus `MAIN_MODULE` — a router defined in any *other* module under
    `apps/platform-api/src/anytoolai_platform_api/` (e.g. a hypothetical `product_api.py` with
    `router = APIRouter(prefix="/proposal_ai")`, then wired in via `app.include_router(router)`
    from `main.py`) was never visited at all, since neither `main.py` (no forbidden literal there)
    nor `routers/` (the file isn't under it) would catch it. Fixed: replaced the two-source scan
    with one `PLATFORM_API_PACKAGE.rglob("*.py")` over the whole package (7 non-router `.py` files
    today — `bootstrap.py`, `dependencies.py`, `errors.py`, `main.py`, `migrate.py`, `schemas.py`,
    `settings.py` — plus `routers/*.py` and `middleware/`/`openapi/` subpackages), so any module
    anywhere in the package is covered, not just the two previously-assumed locations. Verified
    with a synthetic two-file package (`product_api.py` defining the router,
    `main.py` only `include_router`-ing it) reproducing the exact review scenario: the old
    scan scope found nothing, the new whole-package scan finds both the forbidden prefix and path.
  - **Non-blocking.** `_quoted_string_spans` (used by the URL-query exemption) still used the old
    1-char-only `_QUOTE_CHARS` tracker even after `_strip_comments` gained triple-quote support in
    round 12 — so a real triple-quoted string with an interior quote before a URL query value
    (`callback = """quoted " then https://x?model=openai/y"""`) closed its span early, and
    `_is_url_query_value` stopped recognizing the match as URL content, false-positiving it as a
    hardcode. Fixed: moved `_TRIPLE_QUOTES` above both functions and gave `_quoted_string_spans`
    the identical triple-quote-first delimiter check `_strip_comments` uses, instead of
    maintaining two independently-drifting copies of the same tracking logic. Verified the exact
    case from the review no longer false-positives, re-ran the full 19-case regression table (now
    20 cases, rounds 4–13) to confirm nothing else flipped.
  - Caught and fixed a self-inflicted syntax bug mid-edit (again): a new docstring embedded a
    literal `"""` inside its own `"""`-delimited docstring, closing it early — same mistake as
    round 12, caught by running `ast.parse` on the file before moving on this time too.
- [x] Tenth GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #9)", reviewing commit
      `f96d571`) found two more findings in the same two categories that had already produced
      real bugs across rounds 3/4/6/7/8/9/11/12/13 — router-identity tracking, and hand-rolled
      comment/string handling. Rather than add an eleventh special case to either hand-rolled
      tracker, this round replaced the underlying approach for the categories that had actually
      produced repeat bugs:
  - **`test_no_product_specific_endpoints.py`.** `_router_variable_names` only recorded a name
    whose RHS was a direct `APIRouter(...)`/`FastAPI(...)` constructor call — a plain rebinding
    (`router = APIRouter(); api = router`) left `api` untracked, so `@api.get(...)` was invisible.
    Fixed with a fixed-point propagation pass added to `_router_variable_names`: after the direct
    constructor-call pass, repeatedly scan `Assign`/`AnnAssign` nodes whose RHS is already a known
    router expression (via the existing `_is_router_expr`, which also covers `.router` access) and
    add their LHS name(s), until a full pass adds nothing new. This resolves not just a single
    rebinding but an arbitrary-length alias chain (`b = a; c = b; ...`) in one mechanism, since the
    review's exact example is really just the 1-hop case of a general problem. Verified the exact
    `api = router` case, the equivalent `other_app = app`, and an unrequested 2-hop chain
    (`b = router; c = b`) are all now caught.
  - **`test_litellm_model_strings_stay_in_provider_config.py`.** `#` inside a YAML block scalar
    (`|`/`>`) is literal content, not a comment — `notes: |\n  # fallback openai/gpt-4.1` was
    truncated at the block scalar's leading `#`, hiding the real hardcode. This is the same root
    cause as rounds 7/9/11/12/13's Python triple-quote/multi-line findings: a hand-rolled
    line-based tracker approximating a real language's string/comment grammar will always have
    another edge case, because it fundamentally isn't that grammar. Both languages already have a
    correct, already-available implementation of their own grammar: `tokenize` (stdlib) for
    Python, `yaml.compose` (PyYAML — already a project dependency via
    `packages/backend/platform-core`) for YAML. Replaced the Python and YAML scanning paths with
    real-parser-based ones: `.py` files are scanned via `tokenize.generate_tokens`, checking only
    `STRING` token values (decoded with `ast.literal_eval`) — `COMMENT` tokens are structurally
    excluded from consideration, not hand-detected; `.yaml`/`.yml` files are scanned via
    `yaml.compose`'s node graph, checking each `ScalarNode.value` (block/flow, quoted/unquoted —
    all resolved correctly by the real parser, with no separate comment-stripping needed). `.json`
    (no comment syntax, always-quoted strings — never actually buggy) and `.js`/`.ts`-family files
    (no stdlib tokenizer available without a new dependency) keep the existing hand-rolled
    line-based scanner, now isolated to only the two file types it was ever actually shown to be
    unreliable for after this change removes the two that were provably wrong. Caught and fixed a
    self-introduced regression while rewriting: `_is_url_query_value`'s span-containment check used
    the wrong boundary (`start <= position`) for a quoted span, since the *match* position is the
    quote character itself, one position *before* the span's own content start (`content_start =
    i + 1`) — off by one, caught by re-running the full regression table before treating the
    rewrite as done, not shipped blind. Verified the exact round-14 YAML block-scalar case, all 20
    prior regression cases (rounds 4–13, now spread across three dedicated Python/YAML/regex
    check functions), and 3 new cases the rewrite specifically needed (a plain string with no
    provider match, a real YAML comment, a JS/TS URL-query false positive) — 23 cases total, none
    flipped. Also ran the real test against the actual repository tree (not just the synthetic
    cases) to confirm the wider/different scanning mechanism doesn't newly false-positive on real
    project files.
- [x] Eleventh GitHub PR review round (2026-08-31, PR #96 "Code-ewview (me #10)", reviewing
      commit `ae67858`) found 4 more findings — 2 in each file, all in the round-10 rewrite
      itself. This time, before touching any code, entered plan mode at the user's explicit
      request, wrote and verified a design (see `docs/exec-plans/active/` — the design is
      recorded below, not as a separate file) *before* implementing, including a documented
      decision to reject a tempting alternative (see the decision-log entry on dynamic FastAPI
      introspection) after concretely verifying it would introduce worse fragility than it fixed:
  - **`test_no_product_specific_endpoints.py`, blocking.** Router identity tracking was still
    per-file only: `from anytoolai_platform_api.routers.demo import router as demo_router` — the
    exact pattern `main.py` already uses for all 7 real routers — left the imported name
    untracked in the importing file, so a hypothetical direct `@router.get(...)` call there
    (rather than only `app.include_router(...)`, which `main.py` happens to use today) would be
    invisible. Fixed: split `_router_variable_names` into `_direct_router_names` (unchanged
    constructor-call pass) and `_propagate_router_aliases` (unchanged local-rebinding pass, now
    reusable against a pre-seeded set); added `_module_dotted_name`/`_resolve_import_module`
    (handles both absolute imports — verified against real `main.py`, resolving all 7 real
    `router as X_router` imports to their source files — and relative imports via `node.level`)
    and `_package_router_names`, which runs one whole-package fixed point combining cross-file
    import-edge propagation with the existing per-file alias propagation, so any-length chains
    (import then local re-alias, multi-file import chains) resolve, not just the one reported
    hop. `test_no_product_specific_endpoint_paths()` now parses every file once, computes
    `router_names` for the whole package once, then calls a renamed
    `_route_path_literals_for_tree` per file with the precomputed pieces — and raises a clear
    `AssertionError` on a `SyntaxError` instead of silently skipping an unparseable file. Verified
    the exact review scenario (relative import), the real `main.py`-shaped absolute-import-with-
    alias pattern, a 3-file import chain, and an import-then-local-re-alias combo — plus two
    control cases (an unrelated cross-module import that isn't a router; a `main.py`-shaped file
    using only `include_router`) confirming no new false positives.
  - **Same file, blocking.** `ROUTE_REGISTRATION_METHODS` covered only HTTP methods; FastAPI's
    WebSocket registration APIs (`websocket`, `websocket_route`, `add_api_websocket_route`,
    `add_websocket_route`) were ignored entirely. Fixed: added all four — verified each exists on
    this project's installed FastAPI (0.137.0) with `path: str` as the first positional argument,
    so the existing `_path_argument` extraction needed no changes. These automatically benefit
    from fix one's whole-package router-identity resolution with no separate handling.
  - **`test_litellm_model_strings_stay_in_provider_config.py`, blocking.** The round-10
    `tokenize`-based Python scanner only inspected `STRING` tokens; Python 3.12+ tokenizes an
    f-string as `FSTRING_START`/`MIDDLE`/`END` instead, so `model = f"openai/gpt-4.1"` — a
    regression versus the original regex scanner, which would have caught it — was invisible.
    Fixed by switching `_python_offender` from `tokenize` to `ast.walk` entirely (not just to
    handle f-strings — a strictly more robust primitive for this problem: `JoinedStr`/`Constant`/
    `FormattedValue` shapes are stable across Python versions, unaffected by tokenizer-level
    changes; gives already-decoded values with no `ast.literal_eval` failure modes; comments don't
    exist in the AST at all, excluding them by construction the same way `tokenize.COMMENT`-
    skipping did). A `JoinedStr` is only checked when every part is a literal `Constant` (no
    `FormattedValue`, i.e. no real `{expr}` interpolation) — a genuinely dynamic f-string is
    skipped, matching the original intent. `tokenize`/`io`/`ast.literal_eval` are now unused and
    removed. Verified the exact `f"openai/gpt-4.1"` case, a genuinely dynamic
    `f"openai/{name}-v1"` (correctly skipped), and all 12 prior Python regression cases (including
    the round-13 triple-quote-with-interior-quote case and the round-9 docstring-control case).
  - **Same file, blocking.** `yaml.compose()` only accepts a single YAML document; a valid
    multi-document file (`foo: bar\n---\nmodel: openai/gpt-4.1`) raised `YAMLError`, and `except
    yaml.YAMLError: return None` silently skipped the *entire file* — a worse failure mode than
    the pre-round-10 line scanner, which still scanned every line regardless of document
    structure. Fixed: switched to `yaml.compose_all`, iterating every document (verified
    `compose_all` keeps line numbers absolute across `---` boundaries, not reset per document); a
    genuine parse failure now raises `AssertionError` instead of silently skipping, matching this
    repo's anti-silent-skip convention and the review's own suggestion — verified safe by running
    `yaml.compose_all` against all 27 real `.yaml`/`.yml` files in `SCAN_ROOTS` first (zero parse
    failures), so this can't newly break on anything that exists today. Verified the exact
    multi-document case plus all 5 prior YAML regression cases.
  - Re-ran the full 20-case Python/regex regression table plus the 5-case YAML table from round
    10 (25 cases total, all pass) and both test files against the real repository tree, in
    addition to the new-case verification above.
- **Twelfth GitHub PR review round** ("Code-ewview (me #11)", reviewing commit `b000675`) — two
  more findings, both verified against current code before touching anything (reproduced each
  exact failure with a standalone script first, per the established "verify before fixing"
  discipline):
  - **`test_no_product_specific_endpoints.py`, blocking.** `_resolve_import_module`'s relative-
    import resolution was wrong for a package's `__init__.py`: `_module_dotted_name` already
    drops the trailing `__init__` for that file (so `routers/__init__.py` maps to
    `anytoolai_platform_api.routers`), but `_resolve_import_module` then unconditionally computed
    `parts[:-1]` — correct for an ordinary module (whose own dotted name still has its own
    basename attached, so dropping one component reaches its *containing* package), but wrong for
    `__init__.py`, whose dotted name already *is* the package itself, not a module inside it.
    `from .proposal import router` inside `routers/__init__.py` resolved to
    `anytoolai_platform_api.proposal` instead of `anytoolai_platform_api.routers.proposal`,
    silently breaking a normal re-export chain (`routers/proposal.py` defines the router,
    `routers/__init__.py` re-exports it, a third module imports it via the package and registers a
    product-specific route) — reproduced exactly as described, then fixed by branching on
    `importing_path.name == "__init__.py"`: for an `__init__.py`, level-1 stays at its own dotted
    name (already the package); for an ordinary module, level-1 drops to its containing package,
    unchanged from before. Verified: the exact re-export-through-`__init__.py` chain now resolves
    end-to-end (three-file synthetic package: `routers/proposal.py` → `routers/__init__.py` → a
    consuming module registering `/proposal_ai/status`, now caught); a level-2 relative import
    from an ordinary module (unaffected, still correct); a level-2 relative import from an
    `__init__.py` (also correct — walks up one additional package level from the package itself);
    the existing absolute-import case (`main.py`'s real pattern, unaffected).
  - **`test_litellm_model_strings_stay_in_provider_config.py`, blocking.** `_strip_comments`
    modeled only JS/TS line comments (`//`), not `/* ... */` block comments — and a stray quote
    character *inside* an unrecognized block comment (e.g. `/* " */`) opened `in_string` early,
    so a later, legitimately-quoted `//` (inside a real URL string) got misread as a line-comment
    start, truncating the rest of the line — including a real hardcode past it. Reproduced the
    review's exact case first (`/* " */ const callback = "https://example.com"; const model =
    "openai/gpt-4.1";` truncated to `/* " */ const callback = "https:` before the fix). Fixed by
    adding a third state (`in_block_comment`, alongside `in_string`) to the existing
    quote-state-carrying scanner: `/*` (when not already inside a string) starts it, `*/` ends it,
    and characters inside are dropped without being interpreted as quotes/line-comment starts —
    the same reason the earlier per-line reset was wrong for multi-line strings (round 11) applies
    here too, so block comments spanning multiple physical lines are handled by the same
    character-at-a-time loop rather than a separate pass. Only fires when `markers` is non-empty,
    which today only happens for the JS/TS-family suffixes (`.json` has no comment syntax and
    returns early, unaffected). Verified: the exact review case now finds the real
    `openai/gpt-4.1` hardcode; a block comment spanning multiple physical lines (correct line
    number reported); an unterminated block comment (no crash/infinite loop, treated as a comment
    to end of file); a real hardcode followed by a trailing block comment on the same line (still
    caught); the pre-existing line-comment-inside-a-string regression case from round 7
    (unaffected).
  - Re-ran the full 24-pass `pytest tests/architecture` suite (unaffected files untouched) and
    both changed test files against the real repository tree.
- **Thirteenth GitHub PR review round** ("Code-ewview (me #12)", reviewing commit `c66f485`) —
  two more findings, both against the same two files the round-11/round-12 rounds already
  extended, both reproduced with standalone scripts before touching code:
  - **`test_no_product_specific_endpoints.py`, blocking.** Whole-package router propagation
    (`_package_router_names`) only built import edges from `ast.ImportFrom` — it never inspected
    `ast.Import`, so a module imported *as an object* (`import
    anytoolai_platform_api.shared as shared` then `@shared.router.get(...)`) left the router
    invisible: `_is_router_expr` recursed on `Attribute(attr="router", value=Name("shared"))` down
    to `Name("shared")`, which was never a tracked router name (it's a module alias, a
    structurally different kind of identity). Root cause: the round-11 whole-package resolver was
    built to close the *exact* reported example (`from .shared import router`) rather than the
    full, closed set of ways Python lets an identity flow between modules — `ast.ImportFrom` and
    `ast.Import` are the only two AST node shapes for that, and only one was modeled. Fixed by
    adding `_module_import_aliases` (maps a local `import X as Y` name to X's dotted module name)
    and `_module_router_names_by_file` (resolves that to the target module's known router names),
    threaded through `_is_router_expr`'s new `module_router_names` parameter — checked before the
    existing `.router` recursion, since `shared.router` must resolve via the module-alias path,
    not by asking "is `shared` itself a tracked router name?" — and through
    `_propagate_router_aliases` and `_package_router_names`'s fixed-point loop (recomputed each
    iteration, since a module-alias target's own router set can still be growing) so
    `_package_router_names` now returns `(router_names_by_file, module_router_names_by_file)`.
    Explicitly left out of scope and documented in `_module_import_aliases`'s docstring: bare
    `import X.Y.Z` without `as` (binds only the top-level package name, needing multi-level
    attribute-chain resolution) and `from . import name` (statically ambiguous between "a
    submodule" and "a name in `__init__.py`" without also consulting the filesystem) — neither
    form is used anywhere in this repo today (verified). Verified: the exact
    `import ... as shared; shared.router.get(...)` case now resolves; a control case (an unrelated
    module import, no router) stays clean; `app.router.add_api_route(...)` (round-10's finding,
    unaffected by the branch reorder in `_is_router_expr`) and a websocket registered through a
    module alias (combining this fix with round-11's WebSocket methods) both still resolve
    correctly; the documented-out-of-scope bare-import case is confirmed to stay unresolved, as
    intended.
  - **`test_litellm_model_strings_stay_in_provider_config.py`, blocking.** The JS/TS scanner
    modeled quotes, line comments, and (as of round 12) block comments, but not regex literals —
    a stray quote inside an unrecognized `/regex/` (e.g. `/"/`, the review's exact example)
    desynced quote-tracking the same way an unrecognized block comment did in round 12, truncating
    a real hardcode past a later, legitimately-quoted `//`. Root cause: this is the exact failure
    mode the round-10 decision log predicted and explicitly accepted when it kept the JS/TS path
    on a hand-rolled scanner instead of a real parser ("keeps the same class of bug... upgrade
    path: parse with a real JS/TS tokenizer if a bug is ever found here") — this is now the third
    hand-rolled-JS/TS-lexer finding (round 3's backtick strings, round 11's block comments, this
    regex-literal gap), the same pattern that already justified moving Python/YAML onto real
    parsers in round 10. Fixed with the standard JS/TS division-vs-regex lexer heuristic rather
    than a full tokenizer: added `_REGEX_PRECEDED_BY_VALUE` (identifier/digit/`)`/`]`/quote chars
    — i.e. "the previous token was a value") and `_regex_literal_end` (finds a regex literal's
    closing, unescaped `/` outside a `[...]` character class), wired into `_strip_comments` via a
    new `last_sig` state variable tracking the last significant character seen. A `/` is treated
    as a regex-literal start (and its content skipped as one unit, like a block comment) only when
    the preceding significant character is *not* a value character; otherwise it's ordinary
    division and falls through unchanged. Verified: the exact review case now finds the hardcode;
    plain division (`a / b / c`, after a number, after `)`/`]`) is unaffected; a regex containing
    an escaped slash and a regex containing a `[...]`-class slash are both correctly skipped as
    whole units; a regex after `,`/`=`/start-of-line is caught. Explicitly left as a known,
    documented gap (checked and confirmed not present in any of the 142 real `.js`/`.ts`-family
    files this test scans today): a *keyword*-preceded regex literal (`return /re/`,
    `typeof /re/`) reads as division, since this is a last-*character* heuristic, not a
    last-*token* one — a keyword like `return` ends in a letter, the same as a real identifier
    would, and distinguishing them needs word-level (not char-level) lookback against a keyword
    set; noted as the upgrade path if this is ever shown to matter. All prior JS/TS regression
    cases (backtick literals, URL-then-model, query-value exemption, JSON-shaped hardcode,
    multi-line template literal, private-class-field `#`) re-verified unaffected.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and both changed test files
    against the real repository tree.

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
- [x] Manual check: synthetic two-file package (`product_api.py` defining
      `router = APIRouter(prefix="/proposal_ai")`, `main.py` only `include_router`-ing it) — the
      old `ROUTERS_DIR` + `MAIN_MODULE` scan scope found nothing; the new
      `PLATFORM_API_PACKAGE.rglob("*.py")` scan finds both `/proposal_ai` and `/status`.
- [x] `python3 -m pytest tests/architecture/test_no_product_specific_endpoints.py -q` against the
      real repo (all 7 non-router `.py` files plus `middleware/`/`openapi/` now included) — passed,
      no false positives from the wider scan.
- [x] Manual check: `callback = """quoted " then https://x?model=openai/y"""` no longer
      false-positives after `_quoted_string_spans` gained triple-quote support; re-ran the full
      19-case regression table (now 20 cases, rounds 4–13) to confirm nothing else flipped.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Manual check: `api = router` + `@api.get(...)`, `other_app = app` + `add_api_route(...)`,
      and an unrequested 2-hop chain `b = router; c = b` + `@c.get(...)` are all now caught by
      `_router_variable_names`'s fixed-point propagation pass.
- [x] Manual check: 23-case regression run against the new `_python_offender`/`_yaml_offender`/
      `_regex_offender` split (20 prior cases from rounds 4–13 plus 3 new ones: a plain no-match
      string, a real YAML comment, a JS/TS URL-query false positive) — all pass, including the
      round-14 YAML block-scalar case. Caught and fixed a self-introduced off-by-one in
      `_is_url_query_value`'s span-containment check during the rewrite, before treating it as
      done.
- [x] `python3 -m pytest tests/architecture/test_litellm_model_strings_stay_in_provider_config.py -q`
      against the real repository tree (not just synthetic cases) — passed, confirming the
      real-parser-based scan doesn't newly false-positive on actual project files.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Before touching code: entered plan mode, verified `_module_dotted_name`/
      `_resolve_import_module` against real `main.py` imports (all 7 real `router as X_router`
      imports correctly resolved to source files), confirmed all 4 WebSocket registration methods
      exist on the installed FastAPI with `path: str` first-positional, prototyped and ran the
      `ast.walk`-based f-string design against the exact and control cases, confirmed
      `yaml.compose_all` keeps absolute line numbers across document boundaries, and confirmed all
      27 real `.yaml`/`.yml` files parse cleanly (so failing loudly on a parse error is safe) —
      all *before* writing the plan file, per the user's explicit request to think and plan first.
- [x] Manual check: the exact round-15 relative-import scenario, the real-`main.py`-shaped
      absolute-import-with-alias pattern, a 3-file import chain, and an import-then-local-re-alias
      combo are all caught; a control case (unrelated cross-module import, not a router) and a
      `main.py`-shaped `include_router`-only file both stay clean (no new false positives).
- [x] Manual check: all 4 WebSocket registration methods (`websocket`, `websocket_route`,
      `add_api_websocket_route`, `add_websocket_route`) are caught when called on a tracked
      router.
- [x] Re-ran all 6 prior `test_no_product_specific_endpoints.py` regression cases (rounds 1–14)
      against the refactored whole-package implementation — all pass, confirming the refactor
      didn't change behavior for any previously-verified case.
- [x] `python3 -m pytest tests/architecture/test_no_product_specific_endpoints.py -q` against the
      real repository tree — passed.
- [x] Manual check: `f"openai/gpt-4.1"` (constant-only f-string) is caught; `f"openai/{name}-v1"`
      (genuinely dynamic) is correctly skipped; re-ran all 12 prior Python regression cases
      (rounds 4–13) against the `ast.walk`-based rewrite — all pass.
- [x] Manual check: `foo: bar\n---\nmodel: openai/gpt-4.1` (multi-document YAML) is caught with
      the correct absolute line number; re-ran all 5 prior YAML regression cases — all pass.
- [x] `python3 -m pytest tests/architecture/test_litellm_model_strings_stay_in_provider_config.py -q`
      against the real repository tree — passed.
- [x] `python3 -m pytest tests/architecture -q`, `validate_architecture.py`, and `quick-check`
      re-run after this round — 24 passed / passed / 981 passed.
- [x] Reproduced both round-12 findings with standalone scripts against current code before
      changing anything: `_resolve_import_module` resolved `from .proposal import router` inside
      `routers/__init__.py` to `anytoolai_platform_api.proposal` (wrong) instead of
      `anytoolai_platform_api.routers.proposal`; `_strip_comments` truncated the exact
      `/* " */ ... "openai/gpt-4.1"` review case before reaching the real hardcode.
- [x] Manual check: `__init__.py` level-1 relative import now resolves within its own package; a
      level-2 relative import from an ordinary module and from an `__init__.py` both resolve
      correctly; the existing absolute-import case (`main.py`'s real pattern) is unaffected.
- [x] Manual check: a synthetic 3-file router re-export chain
      (`routers/proposal.py` → `routers/__init__.py` → a consuming module) now resolves the
      imported router end-to-end and catches its product-specific route.
- [x] Manual check: the exact block-comment review case now finds the real hardcode; a block
      comment spanning multiple physical lines reports the correct line number; an unterminated
      block comment doesn't crash or infinite-loop; a hardcode followed by a trailing block
      comment on the same line is still caught; the round-7 line-comment-inside-a-string
      regression case is unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), both changed files individually
      against the real repository tree, `validate_architecture.py`, `validate-docs`, and
      `quick-check` (981 passed) all green after this round.
- [x] Reproduced both round-13 findings with standalone scripts against current code before
      changing anything: `import anytoolai_platform_api.shared as shared; shared.router.get(...)`
      resolved to no literals at all (the router was invisible); `_strip_comments` truncated the
      exact `/"/`-then-URL review case before the real hardcode.
- [x] Manual check: the exact `import X as Y; Y.router.get(...)` case now resolves; a control case
      (an unrelated module import, not a router) stays clean; `app.router.add_api_route(...)`
      (round-10) and a WebSocket method (round-11) registered through a module alias both still
      resolve; the documented-out-of-scope bare `import X.Y.Z` case is confirmed to stay
      unresolved as intended.
- [x] Manual check: the exact regex-literal review case now finds the hardcode; plain division
      (after a number, an identifier, `)`, `]`) is unaffected; a regex with an escaped slash and
      one with a `[...]`-class slash are both skipped as whole units; a regex after `,`/`=`/
      start-of-line is caught; all prior JS/TS regression cases (backtick, URL-then-model,
      query-value exemption, JSON-shaped hardcode, multi-line template literal, private-class-
      field `#`) stay unaffected; confirmed no file among the 142 real `.js`/`.ts`-family files
      this test scans today contains the documented-out-of-scope keyword-preceded-regex case.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), both changed files against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.

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
| 2026-08-31 | `test_no_product_specific_endpoints.py` scans the entire `apps/platform-api/src/anytoolai_platform_api` package (`PLATFORM_API_PACKAGE.rglob("*.py")`), not just `routers/` + `main.py`. | A route can be registered from any module that gets imported and wired into `app` — the router's own definition site doesn't have to live under `routers/`, and `main.py` doing nothing but `app.include_router(imported_router)` carries no forbidden literal itself; the previous two-source assumption about where a route registration could live was simply wrong, confirmed by the round-13 review's `product_api.py` example. |
| 2026-08-31 | `_TRIPLE_QUOTES` moved above both `_quoted_string_spans` and `_strip_comments`, and both functions now share the identical triple-quote-first delimiter check, instead of each maintaining its own copy. | Round 12 fixed only `_strip_comments`'s copy of this exact tracking logic and the round-12 log entry incorrectly implied `_quoted_string_spans` was fixed too — the same class of "two independent copies of the same state machine drift apart" bug that already bit `SKIP_PATH_PARTS` twice (rounds 1–2) and the receiver/alias checks across `_router_variable_names`/`_route_path_literals` (rounds 10–11). Sharing the constant and the check shape doesn't guarantee no future drift, but removes the most common cause of it (forgetting the sibling copy exists). Superseded by round 10, which moved `.py` off this tracker (and its `_TRIPLE_QUOTES` handling) entirely — see below. |
| 2026-08-31 | `.py` and `.yaml`/`.yml` files are scanned with real parsers (`tokenize`, `yaml.compose`) instead of a hand-rolled line-based quote/comment tracker; `.json`/`.js`-family files keep the hand-rolled tracker. | Nine of the ten review rounds against these two test files (3, 4, 6, 7, 8, 9, 11, 12, 13) found a real bug in hand-rolled string/comment tracking approximating Python or YAML grammar — each fix closed the reported case but the category kept producing a next one, because a line-based approximation of a language's grammar structurally can't be that grammar. Both languages already have a correct, dependency-free (Python: stdlib `tokenize`; YAML: PyYAML, already a project dependency) implementation of their own grammar available, so using it eliminates the *category*, not just the latest instance. `.json` has no comment syntax and only ever quotes strings (the category of bug that hit Python/YAML doesn't exist in JSON's grammar — never actually reported broken); `.js`/`.ts` have no available stdlib tokenizer, so they keep the same class of residual risk the Python/YAML paths were just moved off of, accepted as a known, narrower ceiling rather than rewritten with a new dependency for a file type this audit hasn't found a real bug in yet. |
| 2026-08-31 | `_router_variable_names` propagates router/app identity through simple rebindings (`api = router`) to a fixed point, rather than only recognizing a direct constructor-call RHS. | The round-10 review's `api = router` example is the 1-hop case of a general "alias tracking" problem already hit twice before in narrower forms (round 9's module-qualified access, round 10's import alias) — a fixed-point pass over `Assign`/`AnnAssign` nodes whose RHS is already a known router expression solves the general case (any-length alias chain) in one mechanism instead of adding a third special-cased branch for one more specific rebinding shape. |
| 2026-08-31 | Router-identity resolution stays static (AST over the whole `apps/platform-api` package), rejecting a switch to importing the real `anytoolai_platform_api.main.app` and inspecting its resolved route table. | Investigated before touching code, per the user's explicit "think and plan first" instruction after round 10's rewrite itself produced 4 new gaps. This repo's `fastapi` dependency is unpinned (`fastapi>=0.115`); the installed 0.137.0 defers route flattening behind a private `_IncludedRouter`/`.original_router` indirection, so a correct dynamic table would depend on an internal that can silently change shape on any future FastAPI bump. `app.openapi()` alone (the stable public API) also has blind spots — no WebSocket routes, no `include_in_schema=False` routes. A bounded, inspectable static-analysis gap beats an unbounded private-API fragility risk for a project already burned repeatedly by unreliable detection. |
| 2026-08-31 | Router-name resolution across the whole package (`_package_router_names`) is a single fixed-point loop combining cross-file import-edge propagation and each file's existing local-rebinding propagation, rather than two separate passes run to convergence independently. | A name can become known only after an imported router alias arrives from another file, and that alias can then itself be locally rebound again in the importing file (or re-exported to a third file); running import-edge propagation and local-alias propagation as two independent one-shot passes would miss any chain where the two interleave, so they share one `while changed` loop over both mechanisms. |
| 2026-08-31 | `_resolve_import_module` mimics Python's own relative-import resolution (`node.level`) instead of only handling this repo's actual convention (absolute imports). | The round-10 review's own example used a relative import; the resolution logic is a handful of lines given `_module_dotted_name` already exists, and getting the general case right up front is cheaper than shipping an absolute-only version that the next review round would show incomplete against a relative-import file this repo could add tomorrow. |
| 2026-08-31 | Star imports (`from .shared import *`) and cross-module constant resolution (`_module_string_constants` following an imported constant to its defining module) are explicitly left unhandled this round, documented rather than silently missing. | Neither is used anywhere in this repo today (verified), and both are real added complexity for idioms with no current instance; adding speculative handling for a pattern that hasn't been shown to exist is exactly the scope-creep the "think first" instruction was pushing back against — better to name the gap than pretend the whole-package rewrite makes every future gap in this space impossible. |
| 2026-08-31 | `_python_offender` switches from `tokenize` to `ast.walk` (`ast.Constant`/`ast.JoinedStr`/`ast.FormattedValue`), rather than teaching the `tokenize`-based scanner about `FSTRING_START`/`FSTRING_MIDDLE`/`FSTRING_END` tokens. | PEP 701 (Python 3.12+, this repo runs 3.14) split f-string tokenization into multiple token kinds, which is exactly the kind of version-coupled lexer detail round 10 already moved this file off of once for a different reason; `ast.walk` gives already-decoded string values directly (no `literal_eval`), comments don't exist in the AST at all (excluded by construction), and the node shapes involved have been stable since Python 3.6 — a strictly simpler and more robust primitive than patching the tokenizer-level workaround. A `JoinedStr` with any `FormattedValue` (real `{expr}` interpolation) is left unresolved and skipped, matching the original intent to never evaluate expressions. |
| 2026-08-31 | `_yaml_offender` uses `yaml.compose_all` and raises `AssertionError` on a genuine `yaml.YAMLError`, rather than keeping `yaml.compose` with a silent per-file skip on any parse error. | `yaml.compose` only accepts a single document; a valid multi-document file (`---` separated) raised `YAMLError` and the existing `except yaml.YAMLError: return None` turned that into a silent skip of the *entire file* — worse than the pre-round-10 line scanner, which still scanned every line regardless of document structure, and a direct violation of this repo's own no-silent-skips convention. Verified safe against all 27 real `.yaml`/`.yml` files in `SCAN_ROOTS` before making a parse failure fatal — zero existing files trip it. |
| 2026-08-31 | `_resolve_import_module` branches on `importing_path.name == "__init__.py"` to decide whether level-1 stays at the importing module's own dotted name or drops to its containing package, rather than always dropping one component. | A package's `__init__.py` already represents that package itself (`_module_dotted_name` already strips the trailing `__init__`, matching Python's own `__package__` semantics for a package vs. an ordinary module); always dropping one more component double-counted that for `__init__.py` specifically, silently breaking a common re-export pattern (`__init__.py: from .submodule import x`) that this repo already uses for its own router files. |
| 2026-08-31 | `_strip_comments` tracks JS/TS `/* ... */` block comments as a third explicit state (`in_block_comment`) inside the same character-at-a-time loop, rather than pre-stripping block comments in a separate pass before the existing quote/line-comment scan. | A block comment can contain a stray quote character, and a separate pre-pass would need its own (necessarily incomplete) notion of "am I inside a string" to avoid stripping a `/* ... */`-shaped sequence that's actually inside a real string literal — the same class of two-independent-copies-of-one-state-machine risk already named in the round-9/round-10 decision log entries about `_TRIPLE_QUOTES`. One shared loop with one shared `in_string` check is the only way a block comment inside a string (kept) and a string-like sequence inside a block comment (ignored) are both handled correctly by construction. |
| 2026-08-31 | Whole-package router-identity resolution gains a *second*, independent identity source (`_module_import_aliases`/`_module_router_names_by_file`, for `import X as Y`) alongside the existing `ast.ImportFrom`-based one, rather than trying to unify both import statement forms into one lookup. | `ast.Import` and `ast.ImportFrom` are semantically different at the AST level — one binds a name to a *name defined in* another module, the other binds a name to *the module object itself* (whose attributes are then accessed) — and forcing them through one code path would have made the already-dense `_package_router_names` fixed-point loop harder to follow for a benefit (shared code) that doesn't materialize, since the two only share "feeds into the same `router_names`/`_is_router_expr` check" at the boundary, not their actual resolution logic. |
| 2026-08-31 | `_is_router_expr` checks the module-alias branch (`shared.router` via `import ... as shared`) *before* the existing literal `.router`-attribute recursion, not after. | Both branches can match the same AST shape (`Attribute(attr="router", value=Name(...))`), but mean different things: the `.router` recursion asks "is the *value itself* a tracked router/app name", which is wrong when the value is a module alias (a structurally different kind of identity) — checking module-alias resolution first, and falling back to the `.router` recursion only when it doesn't apply, is what makes `shared.router` (module alias) and `app.router` (local FastAPI app) both resolve correctly through one function instead of one silently shadowing the other's intended case. |
| 2026-08-31 | Bare `import X.Y.Z` (no `as`) and `from . import name` are explicitly left unhandled by the module-alias fix, documented in `_module_import_aliases`'s docstring rather than silently missing. | Bare `import X.Y.Z` binds only the top-level package name in Python's own semantics, needing multi-level attribute-chain resolution (`X.Y.Z.router`, not just `Y.router`) to close correctly; `from . import name` is statically ambiguous between "a submodule named `name`" and "a name defined in `__init__.py`" without also consulting the filesystem. Neither is used anywhere in this repo today (verified) — the same "don't build for a pattern that hasn't been shown to exist" call already made for star imports and cross-module constant resolution in the round-11 decision log. |
| 2026-08-31 | The JS/TS regex-vs-division ambiguity is resolved with the standard last-*character* lexer heuristic (`_REGEX_PRECEDED_BY_VALUE`/`_regex_literal_end`), not a full JS/TS tokenizer, and the resulting keyword-preceded-regex gap (`return /re/`) is documented rather than closed. | This is the third finding against the hand-rolled JS/TS scanner specifically (round 3's backtick strings, round 11's block comments, this regex-literal gap) — the same repeat-failure pattern that already justified moving Python/YAML onto real parsers in round 10 — but unlike Python (`tokenize`) and YAML (already-a-dependency PyYAML), no stdlib or already-a-dependency JS/TS tokenizer exists to switch to without adding a new dependency, so the round-10 "known, narrower ceiling, accepted" tradeoff for this path stands. The character-level heuristic closes the concretely reported case (and the operator/punctuation-preceded cases that are the vast majority of real regex literals) for the cost of a bounded, well-known lexer trick instead of a full parser; the keyword-preceded case it can't distinguish (a keyword and an identifier can end in the same character) was checked against all 142 real `.js`/`.ts`-family files this test scans and confirmed absent today, so closing it now would be exactly the "build for a pattern that hasn't been shown to exist" scope-creep this round's own sibling decision (bare imports, above) argues against. |

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
| 2026-08-31 | Eighth GitHub PR #96 review round ("Code-ewview (me #7)", reviewing commit `8b0b9d4`) found `app.router.add_api_route(...)` — valid FastAPI usage via the app's public `.router` attribute — still bypassed the endpoint guard (receiver was an `ast.Attribute`, not a tracked `ast.Name`), and that the string-tracker's `_QUOTE_CHARS`-only model misreads Python triple-quoted strings as three independent 1-char delimiters, so an interior single `"` inside a triple-quoted body desynced tracking and let a following `#` on the next line be misread as a real comment. This time fixed both with a generalization instead of another one-off special case: `_is_router_expr` (a small recursive router/`.router`-chain check) replaces the direct-`ast.Name`-only receiver check; `_TRIPLE_QUOTES` is checked as an atomic 3-char delimiter before the 1-char fallback. Verified both exact cases from the review, a control case (an ordinary docstring with `#` and the word "model" but no real hardcode stays unflagged), re-ran the full 19-case regression table spanning rounds 4–12 (nothing flipped), and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Ninth GitHub PR #96 review round ("Code-ewview (me #8)", reviewing commit `0b4a469`) found one blocking gap and one non-blocking one: `test_no_product_specific_endpoints.py` only scanned `routers/` + `main.py`, so a router defined in any other package module (e.g. a hypothetical `product_api.py`, wired in from `main.py` via `include_router` alone, which carries no forbidden literal itself) was never visited at all; and `_quoted_string_spans` still used the pre-round-12 1-char-only quote tracker, so a real triple-quoted string with an interior quote before a URL query value false-positived as a hardcode once `_strip_comments` (but not this sibling function) gained triple-quote support. Fixed both: replaced the two-source file scan with `PLATFORM_API_PACKAGE.rglob("*.py")` over the whole package; moved `_TRIPLE_QUOTES` above both quote-tracking functions and gave `_quoted_string_spans` the same triple-quote-first check `_strip_comments` uses, instead of two independently-drifting copies. Also corrected the round-12 log entry's inaccurate claim that both functions had already been fixed together. Caught and fixed a second self-inflicted `"""`-inside-`"""`-docstring syntax bug the same way as round 12 (`ast.parse` before moving on). Verified with a synthetic two-file package reproducing the exact review scenario (old scan: nothing found; new scan: both offenders found) and the exact triple-quote-interior-quote case, re-ran the full 20-case regression table spanning rounds 4–13 (nothing flipped), and `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Tenth GitHub PR #96 review round ("Code-ewview (me #9)", reviewing commit `f96d571`) found two more findings in the same two categories that had already produced repeat bugs across the prior nine rounds: `_router_variable_names` still only recognized a direct constructor-call RHS, so `api = router` left `api` untracked; and `#` inside a YAML block scalar is literal content, not a comment, so `notes: |\n  # fallback openai/gpt-4.1` hid a real hardcode. Rather than add an eleventh special case to either hand-rolled tracker, replaced the underlying approach where it had actually been shown unreliable: `_router_variable_names` gained a fixed-point alias-propagation pass (any-length rebinding chain, not just the one reported); `.py` and `.yaml`/`.yml` scanning moved from the hand-rolled line-based tracker to real parsers (`tokenize` for Python, `yaml.compose` via the already-a-dependency PyYAML for YAML), with `.json`/`.js`-family files kept on the existing tracker since that category of bug was never actually shown to exist there. Caught and fixed a self-introduced off-by-one in `_is_url_query_value`'s span-containment check while rewriting (verified via the regression table before calling it done, not shipped blind). Verified the exact `api = router` case plus an unrequested 2-hop alias chain, the exact YAML block-scalar case, a 23-case regression table (20 prior cases plus 3 new ones the rewrite needed), and a real-repository-tree run of both test files (not just synthetic cases) to confirm no new false positives. `pytest tests/architecture` (24 passed) / `validate-architecture` / `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Eleventh GitHub PR #96 review round ("Code-ewview (me #10)", reviewing commit `ae67858`) found the round-10 rewrite itself left 4 gaps: router-identity tracking was still per-file only, so `main.py`'s real pattern (`from anytoolai_platform_api.routers.demo import router as demo_router`) left every imported router name untracked; `ROUTE_REGISTRATION_METHODS` covered only HTTP methods, missing FastAPI's 4 WebSocket registration APIs entirely; the `tokenize`-based Python scanner only inspected `STRING` tokens, so an f-string hardcode (`f"openai/gpt-4.1"`) was invisible under Python 3.12+'s PEP 701 f-string tokenization (a regression versus the pre-round-10 regex scanner); and `yaml.compose()` raising on a valid multi-document file turned into a silent skip of the entire file via the existing `except yaml.YAMLError: return None`. Given the user's explicit instruction to think and plan before touching code again, entered Plan Mode first: verified all four findings directly against current code, investigated and rejected switching router-identity resolution to dynamic FastAPI app introspection (concrete reason: unpinned `fastapi>=0.115` plus the installed 0.137.0's private `_IncludedRouter`/`.original_router` route-flattening internals — see decision log), and only implemented after presenting a complete plan for approval. Fixed all four: `_package_router_names` resolves router identity across the whole package via a single fixed-point loop combining cross-file import-edge propagation (`_resolve_import_module`, handling both absolute and relative imports) with each file's existing local-rebinding propagation; the 4 WebSocket methods were added to `ROUTE_REGISTRATION_METHODS`; `_python_offender` was rewritten from `tokenize` to `ast.walk` over `ast.Constant`/`ast.JoinedStr`/`ast.FormattedValue` (skips any `JoinedStr` with real `{expr}` interpolation, matching the original intent to never evaluate expressions); `_yaml_offender` switched to `yaml.compose_all` and now raises `AssertionError` on a genuine parse failure instead of skipping. Explicitly left out of scope and documented: star imports and cross-module constant resolution, neither used anywhere in this repo today. Verified: the exact `main.py`-shaped absolute-import pattern, a relative-import variant, a 3-file import chain, an import-then-local-realias combo, and 2 control cases (no false positives) for fix 1; all 4 WebSocket methods for fix 2; the exact f-string case plus a genuinely-dynamic f-string (correctly skipped) for fix 3; the exact multi-document YAML case plus all 27 real repo YAML files (zero parse failures) for fix 4; the full prior regression table (23 cases, rounds 4–14) replayed against every rewritten function with nothing flipped; both test files run against the real repository tree, not just synthetic fixtures. `pytest tests/architecture` (24 passed), `validate_architecture.py`, and `quick-check` (981 passed) stay green. | Await/act on next code review. |
| 2026-08-31 | Twelfth GitHub PR #96 review round ("Code-ewview (me #11)", reviewing commit `b000675`) found two more gaps in the round-11 work: `_resolve_import_module` unconditionally dropped one path component for level-1 relative imports, which is correct for an ordinary module but wrong for a package's `__init__.py` (whose dotted name already IS the package, per `_module_dotted_name`), so `from .proposal import router` inside `routers/__init__.py` resolved to `anytoolai_platform_api.proposal` instead of `anytoolai_platform_api.routers.proposal` — breaking a normal router re-export chain through `__init__.py`; and `_strip_comments` only modeled JS/TS line comments (`//`), not `/* ... */` block comments, so a stray quote inside an unrecognized block comment desynced quote-tracking and caused a later, legitimately-quoted `//` (inside a real URL) to be misread as a line comment, truncating a real hardcode past it. Reproduced both exact cases with standalone scripts before changing anything. Fixed both: `_resolve_import_module` now branches on `importing_path.name == "__init__.py"` (stays at its own dotted name for level-1 instead of dropping a component); `_strip_comments` gained a third state (`in_block_comment`) inside the same character-loop that already carries `in_string` across line boundaries, so a block comment containing a quote and a string containing `/*`-like text are both handled correctly by one shared state machine instead of a second, independently-drifting comment-stripping pass. Verified: the exact re-export-through-`__init__.py` chain (3-file synthetic package) now resolves end-to-end; level-2 relative imports from both an ordinary module and an `__init__.py` stay correct; the existing absolute-import case is unaffected; the exact block-comment review case now finds the hardcode; a block comment spanning multiple physical lines reports the correct line number; an unterminated block comment doesn't hang; a hardcode followed by a trailing same-line block comment is still caught; the round-7 line-comment-inside-a-string case is unaffected. `pytest tests/architecture` (24 passed), both changed files against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Thirteenth GitHub PR #96 review round ("Code-ewview (me #12)", reviewing commit `c66f485`) found two more gaps, both root-caused before fixing (user explicitly asked for the justification): `_package_router_names` only built cross-module identity edges from `ast.ImportFrom`, never `ast.Import`, so `import anytoolai_platform_api.shared as shared; @shared.router.get(...)` left the router invisible — the round-11 resolver was built to close the *exact reported example* rather than the full closed set of Python's two import-statement AST shapes; and the JS/TS scanner still didn't model regex literals, so a stray quote inside an unrecognized `/regex/` (the review's `/"/` example) desynced quote-tracking exactly the way an unrecognized block comment did in round 12 — this is the *third* finding against the hand-rolled JS/TS lexer specifically (round 3 backtick, round 11 block comments, this one), the same repeat-failure pattern that already justified moving Python/YAML onto real parsers in round 10, but explicitly accepted at that time as this path's "known, narrower ceiling" since no dependency-free JS/TS tokenizer is available. Fixed both: added `_module_import_aliases`/`_module_router_names_by_file` (a second, independent identity source for `import X as Y`) threaded through `_is_router_expr` (module-alias branch checked *before* the existing `.router` recursion, since both can match the same AST shape but mean different things) and through `_package_router_names`'s fixed point, which now returns `(router_names_by_file, module_router_names_by_file)`; added the standard JS/TS division-vs-regex lexer heuristic (`_REGEX_PRECEDED_BY_VALUE`/`_regex_literal_end`, tracking a new `last_sig` state variable) to `_strip_comments`, closing the concrete case and every operator/punctuation-preceded regex without a new dependency. Explicitly left out of scope and documented: bare `import X.Y.Z` (no `as`) and `from . import name` (neither used anywhere in this repo today); a keyword-preceded regex literal (`return /re/`) — a last-*character* heuristic can't distinguish a keyword from an identifier ending the same way, confirmed absent from all 142 real `.js`/`.ts`-family files this test scans today. Verified: the exact module-alias case now resolves; a control case (unrelated module import) stays clean; `app.router.add_api_route` (round 10) and a WebSocket method (round 11) through a module alias both still resolve; the exact regex-literal case now finds the hardcode; plain division and all prior JS/TS regression cases are unaffected. `pytest tests/architecture` (24 passed), both changed files against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |

## Open questions

- None.

## Follow-up debt

- None.
