# Execution Plan: ANY-25 A22c MVP-A Boundary Audit

## Status

- State: active
- Owner: agent
- Created: 2026-08-31
- Last updated: 2026-09-03
- Review date: 2026-09-03
- Next action: none — implementation, three internal code-review rounds, and twenty-three GitHub
  PR review rounds of fixes landed (round 10 replaced the hand-rolled Python/YAML lexer with real
  parsers; round 11 extended router-identity resolution to the whole package and fixed two gaps
  that rewrite itself exposed; round 12 fixed a `__init__.py` relative-import edge case in that
  same resolution and a JS/TS block-comment gap; round 13 added a second router-identity source
  for module-qualified imports and a JS/TS regex-literal heuristic; round 14 closed the two gaps
  round 13 had left explicitly out of scope (`from . import name` as a module import, and a
  keyword-preceded regex literal) after they were escalated as live blockers; round 15
  generalized both round-14 fixes further (absolute/qualified-relative submodule imports, and a
  control-flow condition's closing paren) after review found each was still scoped to only the
  literal reported example; round 16 replaced the JS/TS scanner's line-scoped keyword lookback
  with persistent state after review found it lost a keyword across a line break; round 17
  replaced per-branch opt-in word finalization with a structural, can't-forget-it precondition
  after a third branch turned up missing the same call; round 18 excluded property-name-spelled-
  like-a-keyword from both keyword checks after review found `config.default` misclassified a
  following division as a regex; round 19 excluded JSX/TSX closing tags (`</div>`) from the same
  regex heuristic, scoped to `.jsx`/`.tsx` only; round 20 disabled `//` line-comment recognition
  entirely for JSX-capable files rather than hand-rolling JSX-text-vs-JS-expression tracking;
  round 21 replaced that fix's own flawed implementation (comment text falling through to the
  ordinary lexer) with a genuine, verbatim-consuming `in_line_comment` state after review found it
  could silently swallow the rest of the file; round 22 gave `/*` the same "ordinary text, not a
  real comment" treatment for JSX-capable files, then self-caught and fixed a second bug the same
  fix introduced (a genuine block comment's own `*/` misread as a fake regex start) before the
  round closed; round 23 closed the whole "misdetected regex silently discards content" class for
  JSX-capable files (never discard a detected span's characters, only ever recognize-and-keep) per
  the review's own explicit conservative-policy suggestion, rather than enumerating one more
  specific shape; round 24 (a new "team lead" reviewer persona's first pass) fixed three real
  gaps in the two new scanners themselves — `add_route`/`mount` missing from the route-method
  allowlist, `scripts/` missing from the LiteLLM scanner's scan roots, and compile-time string
  concatenation bypassing the LiteLLM scanner in both Python and JS/TS — and initially scoped out
  three findings against pre-existing, PR-untouched test files or asking for a large non-blocking
  fixture suite; round 25 escalated two of those three as genuinely required by the ticket's own
  AC regardless of which file implements them, and both are now implemented for real — JS/TS
  provider-SDK-import and raw-provider-API-host detection in
  `test_no_direct_provider_calls_outside_gateway.py`, structural system-role message-shape
  detection in `test_no_prompts_inside_extensions.py` — plus generalized the JS/TS string-concat
  fold from same-line-only to whole-file (multi-line and grouping-paren shapes); round 26 closed
  two more real gaps in round 25's own new checks — the Python provider-SDK boundary only covered
  `openai`/`litellm`, missing `anthropic`/`google.genai`/`cohere`/`mistralai`, and the JS/TS
  import-specifier regex missed bare side-effect (`import "pkg"`) and dynamic (`import("pkg")`)
  imports, only recognizing `from`/`require(`; round 27 closed two more real gaps in round 26's
  own new checks — `_imports_module` didn't resolve `from google import genai` back to
  `google.genai`, and the JS/TS import regex didn't accept a no-interpolation template-literal
  specifier (`` import(`openai`) ``); round 28 closed one more real gap in the same JS/TS import
  guard — `require`/`import` weren't recognized with whitespace before their `(`
  (`require ("pkg")`); round 29 closed a subpath-import bypass in the same guard (`openai/resources/...`
  matched no bare package name in `PROVIDER_JS_PACKAGES`); round 30 closed five more real gaps —
  string-concatenated route paths/constants and Starlette `Route`/`WebSocketRoute`/`Mount`
  route-object composition in `test_no_product_specific_endpoints.py`, and three independently
  drifted JS-extension sets missing `.mjs`/`.cjs` (`test_no_prompts_inside_extensions.py`'s
  scanned suffixes, and the JS-SDK-import/LiteLLM scanners' own sets — now centralized into one
  public `JS_TS_EXTS`); round 31 was a stale repeat of round 30's already-fixed findings (no
  change needed); round 32 closed one more real gap — `_string_value` didn't fold a no-interpolation
  f-string (`ast.JoinedStr`), inconsistent with the LiteLLM scanner's identical rule in the same
  PR; round 33 extended that fold to a `FormattedValue` interpolating an already-known constant
  (`f"/{PRODUCT}/status"`), rejecting a conversion flag or format spec as unresolvable rather than
  guessed at; round 34 (a "team lead" reviewer's third pass, four blocking findings all of the
  same root cause — each gate resolved "what string can this expression be" with its own,
  differently incomplete logic) replaced all four ad-hoc resolvers with one shared static
  resolver, `tests/architecture/static_string_resolution.py` (Python: module constants
  propagated across imports/module aliases to a fixed point, `+`/f-string folding; JS/TS:
  `const`/`let`/`var` bindings propagated across relative named imports, `+`/parens/`${NAME}`
  template folding), wired every gate onto it, and landed the long-deferred permanent isolated
  `tmp_path` regressions (10 new tests); the follow-up-debt list is now empty — see those
  entries); round 35 found three more real gaps, all in the round-34 resolver/gate code itself —
  JS/TS ES2015 shorthand properties (`{ role, content }`) bypassed the extension-prompt gate
  entirely, function-local Python imports could pollute a module's own top-level constants in the
  shared resolver, and the provider-host gate excluded allowed-root files from the resolver's
  input graph instead of only from its reporting, making a host fragment imported from an allowed
  gateway module unresolvable everywhere — all three fixed at the root, with regressions; round 36
  found two more real gaps, both in the round-34 JS/TS resolver's design — a flat, unscoped
  per-file constant namespace let a nested-function `const`/`let` of the same name silently
  overwrite (not merely shadow-within-its-own-scope) a module-level binding's resolved value, and
  treated `let`/`var` as permanently immutable so a later plain reassignment was invisible,
  letting the resolver fold a *wrong* (stale) value instead of the real one — and JSX/TSX
  request-key detection didn't tolerate the block comment `strip_js_comments` deliberately
  preserves in a `.tsx` file, which a real request property can legitimately contain. Fixed by
  making the JS/TS resolver genuinely lexically scope- and mutation-aware (`resolve_js_identifier`
  walks a stack of `{ ... }` block ids, picks the innermost enclosing declaration, and treats a
  reassigned `let`/`var` as unresolvable rather than trusting its initializer) and by making the
  two request-key regexes comment-tolerant; round 37 found the reassignment fix itself was too
  conservative — invalidating a reassigned `let`/`var` entirely made a *deterministically*
  reassigned real value (`let role = "user"; role = "system";`, statically "system" at every use
  site after it) invisible to the gates too, the opposite failure mode from round 36's — and that
  function/arrow parameter defaults (`function f(role = "system") { ... }`) weren't modeled as
  bindings at all. Replaced per-binding single-value tracking with a write timeline (declaration
  or parameter default, then any later reachable reassignment, each `(position, value)`) so
  resolution takes the latest write at or before the actual use site instead of "was this ever
  reassigned"; added parameter-default detection (function and arrow signatures with a real `{
  ... }` body) feeding the same timeline/scope machinery; round 38 found that round 37's timeline
  model still collapsed every write — including one inside `if`/loop control flow that might not
  execute — into a single deterministic value keyed only by textual order, hiding a value still
  reachable at runtime when a later conditional write doesn't run. Replaced single-value timeline
  entries with per-write possible-value sets, distinguishing a write at the binding's own block
  path (deterministic — replaces the reachable set) from one at a strictly deeper path
  (conditional — adds to it without discarding what came before), and propagated multi-valued
  resolution through `+`/template-literal folding via a capped Cartesian-product combine; round
  39 found the deterministic-vs-conditional distinction itself only looked at `{}` block depth,
  so a braceless single-statement control-flow body (`if (cond) role = "x";`, `while (cond) x =
  "y";` — valid JS/TS with no braces at all) had the exact same block path as the surrounding
  code and was wrongly treated as deterministic. Extended `_js_block_path_at` to push a "virtual"
  block (deepening the path exactly like a real `{}` would) immediately after an
  `if`/`for`/`while`'s guard clause or a bare `else` whenever no `{` follows, closing it at that
  single statement's own terminating `;` — correctly handling chained braceless constructs
  (`if (a) if (b) x = 1;`) and `for`/`while` guard clauses' own internal semicolons; round 40
  found a concise (expression-bodied) arrow function's default parameter still wasn't modeled —
  `(provider = "openai") => provider + "/gpt-4.1"` has no `{ ... }` at all for the parameter's
  scope to anchor to — and that the pre-existing brace-detection for a *braced* arrow/function
  body was itself a naive `text.find("{", ...)` that could latch onto an unrelated `{` (a
  template literal's own `${`, a parenthesized object literal) rather than the real body.
  Extended `_js_block_path_at` to push a virtual scope right after `=>` when not immediately
  followed by `{` (the identical mechanism round 39 already gave braceless control flow), and
  rewrote `_js_param_default_events` to anchor an arrow's parameter scope by checking only the
  token immediately after `=>` (matching the resolver's own rule exactly, instead of guessing via
  a forward search); round 41 found the new virtual-scope mechanism itself only closed a
  concise-arrow's scope at `;`/`}`, but a concise arrow is an *expression*, not a statement, and
  can end other ways a bare `;`/`}` check misses — a `,` in an enclosing array/call, the
  enclosing bracket's own closing `)`/`]` with no trailing comma, or ASI at a newline with no
  brackets open — letting the parameter leak past the arrow's real end and shadow an outer
  same-named binding. Added a unified `(`/`[` bracket-depth counter (tracked separately from real
  `{}` block nesting) so every virtual scope — control-flow or arrow-body — now closes at
  whichever comes first: `;`/newline at global bracket depth 0, a comma at exactly its own
  opening bracket depth, or a `)`/`]` that drops bracket depth below it; a `body_starts_at`
  position on each virtual entry prevents the newline/ASI rule from firing prematurely on the
  whitespace between a guard/`=>` and a body that starts on the next line; round 42 found the
  bracket-depth counter deliberately excluded `{`/`}` (round 41's own documented ceiling, since a
  real statement block and an object literal share identical syntax), so a comma separating two
  object-literal properties — `{ normalize: (provider = "x") => provider, model: ... }` — never
  closed a concise arrow's virtual scope, leaking its parameter into a sibling property reading
  the real outer binding. Closed by classifying each `{` via the last significant character
  before it (mirroring how this file already resolves the regex-vs-division ambiguity
  elsewhere): a `{` immediately preceded by `)` — a function/if/for/while/catch header's own
  closing paren — stays a plain block; every other `{` also counts toward bracket depth like
  `(`/`[`, closed by its own matching `}`. The remaining, narrower misclassification (a bare
  block statement, or `try`/`catch`/`finally`/`do`/`else`/class body with no parenthesized header
  right before it) only risks losing precision *inside* that one block, never leaking a scope
  further, so it's accepted as a documented ceiling rather than chased further; after round 42's
  fix, the user directly pointed out that three consecutive rounds (39, 40, 42) had each been
  told — as an explicit alternative in the review text itself — that a real JS/TS parser would
  close this whole class of bug, and each time a bounded heuristic was chosen instead; round 43
  replaced the entire hand-rolled JS/TS scanner (`strip_js_comments`, `_js_block_path_at`, the
  whole timeline/virtual-scope machinery — ~880 lines) with `scripts/agent/js_scope_resolver.mjs`,
  which parses every file with the real TypeScript compiler (`typescript`, already a repo
  devDependency — no new dependency added) and resolves scope, shadowing, write order, and
  conditional branches from real AST parent pointers instead of approximated text positions. This
  closes round 42's own remaining ceiling and every other documented JS/TS ceiling from rounds
  36-42 (including two — the `do`-loop braceless body, and an object-literal comma nested inside
  a non-`)`-preceded block — that were never even reported as bugs, just accepted limitations);
  round 44 found one real gap in the new AST-based `isDeterministicWrite` itself — it checked for
  a conditional slot or a nested `Block` boundary, but not a nested *function/arrow* boundary, so
  a write inside an uncalled concise arrow (`const setFallback = () => provider = "internal";`,
  no `Block` at all to catch it) was wrongly read as deterministic just because its source
  position preceded the use site, exactly as if defining a function were the same as calling it.
  Fixed by adding the missing check (any function-like node crossed on the way up, other than the
  binding's own scope, makes the write conditional — the same call a *braced* arrow/function
  already got for free via its own Block not being `scope`); round 45 found round 43's own "no
  new dependency added" claim broke CI — quick-check's baseline job (the required PR check, run
  on a matrix including `windows-latest`) never runs `pnpm install`, so the repo root's
  `node_modules/typescript` the resolver relied on genuinely didn't exist there, failing every
  JS/TS-touching architecture test with `ERR_MODULE_NOT_FOUND`. Fixed with a standalone
  `scripts/agent/package.json` pinning `typescript` on its own, installed via a plain `npm
  install` that `static_string_resolution.py` self-triggers on first use and caches via a
  package.json-hash fingerprint — mirroring exactly how `.quick-check-venv` self-manages the
  Python side — so quick-check stays self-contained with no CI workflow change (GitHub-hosted
  runners already ship Node.js/npm with no setup step). `node`/`npm` moved from
  `runner.py`'s `OPTIONAL_TOOLS` to `REQUIRED_TOOLS` to match; round 46 found three more real
  gaps in the AST resolver itself: `foldExprInner` didn't unwrap TypeScript-only wrapper
  expressions (`as const`, `satisfies`, the legacy `<Type>` cast, `!`), so a value wrapped in one
  of these — ordinary, already-used-in-this-repo syntax — was dropped entirely; `var` was modeled
  as block-scoped like `let`/`const` instead of function-scoped, so `if (enabled) { var provider
  = "x"; }` made `provider` invisible outside the `if`, and a `for` header's own declaration
  (`for (let provider = "x", i = 0; ...)`) wasn't collected as a binding at all, since only
  `VariableStatement` was visited; and cross-file import resolution was a single eager pass, so a
  multi-hop constant chain (or a barrel `export { a as b } from "./x"` re-export, never even
  registered) resolved correctly only if files happened to be traversed in dependency order.
  Fixed by unwrapping the transparent wrapper kinds before folding; adding `nearestFunctionScope`
  (skips every intervening block/for-header to find the real enclosing function or module scope)
  for `var` declarations and collecting `ForStatement`/`ForInStatement`/`ForOfStatement` headers
  as their own scope nodes; and replacing eager, single-pass import resolution with a lazy
  `redirect` write (resolved on demand, through a real `resolveExport` that follows re-export
  chains with cycle protection) so file traversal order no longer matters and barrel re-exports
  resolve. Round 47 was a second real CI failure, not a review: the round-45 self-install used bare
  `["npm", ...]`/`["node", ...]` with `shell=False`, and Windows `CreateProcess` doesn't apply
  `PATHEXT` the way `shutil.which` does, so `npm` (which ships only as `npm.cmd` there, no `.exe`)
  never resolved on the `baseline` job's `windows-latest` leg even though it was genuinely on
  `PATH`; fixed by resolving both tools through `shutil.which` first, mirroring `probe_tool`'s
  already-correct approach, before invoking them. Round 48 found the last major structural gap in
  the resolver's own binding model: a declaration with no initializer registered no binding at all
  (a later plain assignment had nothing to attach to), and every `var` redeclaration created its
  own separate declaration object instead of contributing to one shared binding, so `resolveDecl`'s
  "last one wins" rule silently discarded every earlier redeclaration's write history; and the
  export resolver still missed a bare same-file `export { name };` (recorded as a self-pointing
  re-export, walking straight into its own cycle guard) and `export * from "./x"` (never read at
  all). Fixed by splitting binding creation from write recording (`addDecl` became a get-or-create
  `binding()`, reused across every redeclaration at the same name/scope) and computing a
  declaration's own initializer determinism for real instead of hardcoding it true; and by
  resolving a bare re-export directly against the already-collected local declaration, and adding
  a `starExports` fallback `resolveExport` tries after a direct name lookup misses. Round 49 was a
  third real CI failure: the `windows-latest` leg's two real-repo-tree tests crashed decoding
  `node`'s UTF-8 JSON output as cp1252 (the Windows default locale encoding) — this repo's own
  prose-heavy comments contain multi-byte UTF-8 sequences cp1252 can't decode at all; fixed by
  passing `encoding="utf-8"` explicitly to both `subprocess.run` calls in
  `static_string_resolution.py`. Round 50 closed two structural false-negatives: a default import
  (`import provider from "./provider"`) and `export default ...;` (an `ExportAssignment`, a
  different AST node the export side never read at all) had no module-graph edge whatsoever,
  fixed by redirecting a default import to a reserved `"default"` export-map name and registering
  `export default <expr>` under that same name; and a braced function's later parameter default
  couldn't see an earlier parameter's binding, since its own ancestor chain never enters the
  function body where parameters were registered — fixed by teaching `nearestScope` to route from
  inside a function's own parameter list to that same body scope. Round 51 found round 50's own
  fix routed parameter defaults into the wrong scope — the function body's `Block`, the same
  object body-local declarations use, so a same-named body-local incorrectly shadowed a parameter
  default's real outer reference; fixed by making the function node itself, not its body, every
  parameter's own scope, and (self-caught while implementing that) fixing a regression it would
  otherwise have introduced in `isDeterministicWrite`'s Block-boundary check for a plain,
  unconditional parameter reassignment inside the body. Round 52 closed the last gap the round-51
  scope split left open: a body `var` redeclaring a parameter's name now starts from that
  parameter's own value at function entry (a new `copyOf` write kind, seeded once when the `var`'s
  binding is first created), matching real JS's `FunctionDeclarationInstantiation` behavior instead
  of treating the redeclaration as an independent, initially-empty binding. Round 53 found the
  deeper cause underneath that: `collectDeclarations` was a single source-order traversal doing
  binding registration and write attachment together, so a `var`'s binding only existed once
  traversal physically reached it — not real hoisting, where the binding exists from function
  entry regardless of where the declaration sits textually; fixed by splitting into two real
  passes (register every binding first, attach every write in a second pass), and (self-caught
  while implementing that) moving round 52's `copyOf` seed into the first pass too, since checking
  "no writes yet" in the second pass could see a pre-declaration assignment's write already
  sitting there and wrongly skip seeding. Round 54 found `isConditionalSlot` recognized only
  conditional *statement* control flow (`if`/loop bodies/`try`/`switch`), never conditional
  *expression* evaluation — a write behind `&&`/`||`/`??`'s short-circuited right side or a
  ternary's untaken branch was wrongly treated as deterministic, discarding the still-reachable
  prior value instead of joining it; fixed by adding an operator-kind-gated check for a
  `BinaryExpression`'s `.right` (only for `&&`/`||`/`??` — not a blanket AST-shape match, since a
  plain `+`'s right side is unconditional) and for a `ConditionalExpression`'s `whenTrue`/
  `whenFalse`. Round 55 was a fourth real CI failure, not a review: `runner.py doctor` timed out
  probing `npm --version` on `windows-latest` — `npm` is itself a Node.js process, and a
  documented Node/Windows quirk makes `process.stdin` access hang when its handle is inherited
  from a non-interactive parent without being explicitly closed; fixed by passing
  `stdin=subprocess.DEVNULL` to `probe_tool`'s call and the round-45 self-install's own `npm
  install` call (the `node ...` call was already safe, since Python's `input=` parameter closes
  its own stdin pipe automatically). Round 56 found compound assignment operators (`+=`, `||=`,
  `&&=`, `??=`) were never recorded as writes at all, and a genuinely self-referential ordinary
  reassignment (`provider = provider + "ai";`) lost its value entirely — resolving the RHS's own
  self-reference used its own literal position, which always included the not-yet-applied write
  itself and hit the fold cycle guard; fixed with a structural (not call-order-dependent)
  `selfReferenceContext` check, plus `+=` (real concatenation via the pre-write value) and
  `||=`/`&&=`/`??=` (always-conditional) write handling, and (self-caught, not from the review) a
  matching short-circuit gap for a nested assignment inside a *compound* logical assignment's own
  RHS. Round 57 found a non-default function parameter was never registered as a binding at all —
  a later deterministic assignment had nowhere to attach, and worse, an unregistered non-default
  parameter let a reference inside the function fall through to shadow a same-named outer binding
  instead of resolving to its own (dynamic) value — a genuine false positive, confirmed via a
  second repro beyond what the review named; fixed by registering every identifier parameter
  unconditionally in the first pass, only gating the *default-value write* (not the binding itself)
  on `param.initializer` in the second. Round 58 found no static member access model existed at
  all — namespace imports (`import * as x from "./y"`) and any `.property`/`["property"]` access
  fell through as unresolved; fixed with `resolveObjectLiteral` (deliberately narrow, single-value
  object resolution) and `resolvePropertyAccess` (resolves through a `NamespaceImport`'s module
  export graph, or through a resolved object literal's own properties), wired into `foldExprInner`
  for both `PropertyAccessExpression` and a statically-keyed `ElementAccessExpression`. Round 59
  was a stale-review no-op (see Progress log) — no code change. Round 60 found round 58's own
  safety check conflated "is the object binding rebound" with "have the object's properties been
  mutated" — a property mutation (`obj.prop = ...`/`obj["prop"] = ...`) was never collected as a
  write at all, so the resolver kept reading a property as permanently equal to its object
  literal's initializer even after an ordinary, deterministic overwrite; fixed with a genuine
  per-property write timeline (`getOrCreatePropertyDecl`, stored directly on the object's own decl
  since properties aren't part of any lexical scope chain) reusing the exact same
  `replayWrites`/`isDeterministicWrite` machinery every other binding goes through, now correctly
  position-aware (a reference before a later mutation sees only the pre-mutation value). Round 61
  found both declaration passes skipped any non-`Identifier` `decl.name`, so destructuring
  (`const { provider } = config;`, `const [primary] = providers;`) registered no binding at all —
  including the same round-57-shaped shadowing false positive on a new binding kind; fixed by
  making declaration collection genuinely recursive over `BindingName`, attaching a
  `destructureFrom` write per directly-named leaf that reuses round 60's mutation-aware
  `resolvePropertyAccess` for object patterns (a new `resolveArrayElement`, no mutation tracking,
  for array patterns); nested patterns and rest elements are registered for shadowing but not
  given a value, an explicit documented narrowing rather than an accidental gap. Round 62 found
  that same recursive handling had been applied only to variable declarations, not the separate
  function-parameter path — and, rather than close one path per review, enumerated and closed
  every place a binding is born (parameters of every function-like kind incl. class methods,
  catch-clause variables, function/class/enum/namespace names) plus every still-fixable ceiling
  (nested destructuring, per-element defaults, object spread, numeric index access/mutation,
  compound member mutation, `enum`/`namespace`/class-`static` members) in one round, all through
  one shared `literalMember`/`getOrCreatePropertyDecl` member model. Round 63 found that member
  model's structural ceiling: its per-property timeline hung off a *single-shape* container, so
  any read that had to cross a container replaced since construction — a nested destructuring's
  intermediate segment (the review's case), a chained `a.b.c` read, a nested member write, a
  spread from a mutated base, a class static replaced then read through — silently read the
  original literal or resolved to nothing; replaced the whole per-property structure with one
  path model (`replayPath`/`exprValues`: every read is `(root binding, key path, position)`, every
  member assignment at any depth is a write on the root binding with its key chain, one replay
  merges both by position, with captured-reference semantics so a mutation of a shared object is
  seen through every path to it while a rebinding/replacement after capture is not), and closed
  the remaining documented ceilings that fell out of it (intermediate-level defaults, rest
  elements, computed keys, ternary/short-circuit values); move to `completed/` once merged.
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
- **Fourteenth GitHub PR review round** (reviewing commit `aa065ea`) — escalation on the two
  round-13 findings: both fixes were only partial, and the two gaps left were the exact
  documented-out-of-scope cases from round 13's own decision log (`from . import shared` and a
  keyword-preceded regex literal). Both reproduced against current code before touching anything;
  both were real, live bypasses (not just theoretical), so this round closes them properly instead
  of re-affirming the earlier scope decision.
  - **`test_no_product_specific_endpoints.py`, blocking.** `from . import shared; shared.router...`
    still bypassed the guard — round 13's `_module_import_aliases` only handled `ast.Import` (`import
    X as Y`), not `ast.ImportFrom` with `node.module is None` (the `from . import name` shape).
    Fixed by extending `_module_import_aliases` (now taking `importing_path`/`module_paths`) to also
    resolve `from . import name`/`from .. import name` as a module identity *when a submodule file
    actually named `name` exists* — checked via `module_paths` lookup on
    `f"{container_dotted}.{alias.name}"`, since Python's own resolution here is genuinely ambiguous
    between "a submodule" and "a name in `__init__.py`" without consulting the filesystem, and a
    real submodule file existing is the only static signal available. When no such submodule file
    exists, the statement is left to the pre-existing `ast.ImportFrom`-based name-edge handling in
    `_package_router_names`, which already correctly covers "a name bound directly inside
    `__init__.py`" — so both sub-cases of the ambiguity are now covered by the mechanism that
    actually matches each. Bare `import X.Y.Z` (no `as`) remains the one still-documented
    out-of-scope case (needs multi-level attribute-chain resolution, not used anywhere in this repo
    today). Verified: the exact `from . import shared` case now resolves; `from .. import shared`
    (two levels) resolves against the correct target; `from . import name` where `name` is a plain
    name bound in `__init__.py` (not a submodule file) still resolves via the pre-existing
    mechanism; a control case (`from . import utils`, not a router) stays clean.
  - **`test_litellm_model_strings_stay_in_provider_config.py`, blocking.** A keyword-preceded
    regex literal (`return /"/`) still bypassed the round-13 heuristic — `_REGEX_PRECEDED_BY_VALUE`
    is a last-*character* check, and `return` ends in a letter the same as any real identifier
    would, so `last_sig not in _REGEX_PRECEDED_BY_VALUE` was false and the `/` was read as
    division, letting the quote inside the (unrecognized) regex desync tracking the same way the
    original round-12 finding did. Fixed by adding `_JS_REGEX_KEYWORDS` (the JS/TS keywords after
    which a value can never precede a `/`) and `_last_word` (reconstructs the identifier word
    ending at the current line's last significant position, skipping trailing whitespace) — when
    the char-level heuristic says "value" and that last character is alphabetic, the whole
    preceding word is now checked against the keyword set, flipping the decision to "regex" when
    it matches. A real identifier (`foo`, or even one that merely starts with a keyword, like
    `returned`) never matches the keyword set, so this only ever makes the heuristic *more*
    permissive toward regex detection, never less. Verified: the exact `return /"/` case now finds
    the hardcode; `typeof`/`instanceof`/`case` keyword-preceded regexes are also caught; a real
    identifier named `returned` (not the keyword `return`) still divides correctly, confirming the
    word-boundary check doesn't just substring-match; all prior regression cases (operator-preceded
    regex, escaped-slash regex, character-class regex, plain division) stay unaffected — the
    escaped-slash case that failed in round 13's ad hoc testing (a shell-escaping artifact in that
    test script, not a real product bug) now also passes cleanly under a corrected test script.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and both changed test files
    against the real repository tree.
- **Fifteenth GitHub PR review round** (repeat review of commit `5d4c6ac9`, submitted as GitHub
  review #5068785118, self-review so posted as COMMENT not REQUEST_CHANGES) — two more gaps, each
  the *generalization* the round-14 fix stopped short of, both reproduced against current code
  before touching anything:
  - **`test_no_product_specific_endpoints.py`, blocking.** Round 14's `_module_import_aliases` fix
    for `from . import name` only matched `ast.ImportFrom` nodes with `node.module is None and
    node.level > 0` — i.e. only the *bare* relative form. An absolute `from
    anytoolai_platform_api.routers import demo` (or a qualified-relative `from .routers import
    demo`) has `node.module` set, so it fell outside that condition entirely and stayed unresolved
    — the same "fixed the exact reported shape, not the general one" mistake named in round 13's
    own root-cause analysis, repeating one level up. Root cause acknowledged directly: the
    determining question — "does `<container>.<name>` match a real submodule file?" — never
    actually depended on whether the import was relative or absolute; narrowing the condition to
    `node.module is None` was an unnecessary, unjustified restriction copied from the literal shape
    of the round-13 review's example rather than derived from the actual logic. Fixed by dropping
    the restriction entirely: every `ast.ImportFrom` (relative or absolute) now gets the same
    submodule-file check. Verified this does *not* regress the actual `main.py` pattern (`from
    anytoolai_platform_api.routers.demo import router as demo_router`, where `router` is a name
    *inside* `demo.py`, not a submodule of it — `candidate_dotted` correctly fails to match any
    file, so this case falls through unchanged to the pre-existing name-edge mechanism) — this was
    the one regression risk worth checking explicitly, since broadening the check could have
    plausibly mis-swallowed the repo's own dominant import pattern. Verified: the exact absolute
    `from package import submodule` case now resolves; a qualified-relative variant resolves; a
    control case (an absolute submodule import that isn't a router) stays clean.
  - **`test_litellm_model_strings_stay_in_provider_config.py`, blocking.** Round 14's regex
    heuristic still treated `)` as always a value-ending character, so `if (ok) /"/.test(input)` —
    a regex literal in *statement position* right after a control-flow condition — was
    misclassified as division, and the quote inside the unrecognized regex desynced tracking the
    same way every prior round's finding in this file did. A condition's closing paren is a
    statement boundary, not a value (`if (cond)` doesn't evaluate to a value the way `foo()`
    does), so `)` needs different treatment depending on what opened its *matching* `(` — a
    distinction the previous character/word-level heuristics couldn't make since they only ever
    looked backward from the `/`, never at paren structure. Fixed by adding `paren_stack: list[bool]`:
    each `(` pushes whether `_last_word(current)` (the word immediately before it) is one of
    `_JS_CONTROL_KEYWORDS_BEFORE_PAREN` (`if`/`while`/`for`/`switch`/`catch`/`with`); its matching
    `)` pops that flag and clears `last_sig` (rather than setting it to `)`) when true, so the
    following `/` reads as a regex start. A plain function-call paren (`foo()`) still marks `)` as
    a value, preserving ordinary division. Verified: the exact `if (ok) /"/...` case now finds the
    hardcode; `while`/`switch`-condition variants are also caught; a real function-call paren still
    divides correctly (`foo(1) / 2`); a real call *inside* a condition body still divides correctly
    after the condition closes (`if (a) { bar() / 2; }`); nested parens (`if ((a && (b))) foo() /
    2;`) resolve the stack correctly; all prior regression cases (keyword-preceded regex,
    operator-preceded regex, escaped-slash/character-class regex, plain division, backtick,
    URL-then-model, block comments) stay unaffected.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and both changed test files
    against the real repository tree.
- **Sixteenth GitHub PR review round** (repeat review of commit `bf66d329`) — the router-identity
  blocker from round 15 is confirmed fixed (thread resolved); one JS/TS scanner finding remains:
  the round-15 control-paren heuristic (`paren_stack`, checking `_last_word(current)`) loses the
  preceding keyword whenever a line break or a line comment separates the keyword from its `(` —
  `current` (the stripped-line accumulator `_last_word` read from) resets at every physical line,
  but `last_sig` persists across lines, so the two drifted out of sync exactly the way this file's
  own decision log has repeatedly warned two independently-updated pieces of state will. Reproduced
  first (`if\n(ok) /"/.test(input); ...; const model = "openai/gpt-4.1";` — the keyword-preceded
  and operator-preceded regex heuristics all correctly fire on one physical line, but split `if`
  onto its own line and the same input truncates the real hardcode again), and a comment-separated
  variant (`if // note\n(ok) ...`) reproduces identically. Root cause was structural, not a
  one-off: `_last_word` was a *lazy*, line-scoped read of `current`, while `last_sig` was
  *incrementally* maintained and persists by construction — anything computed lazily from a
  line-scoped buffer was guaranteed to disagree with `last_sig` the moment a keyword and its
  following token landed on different physical lines. Fixed by replacing the lazy `_last_word`
  read with a persistent tracker: a nested `_note(char)` closure (capturing `last_sig`/`word_buf`/
  `last_word` via `nonlocal`) is now the single call site that updates all three together —
  identifier characters extend `word_buf` and set `last_sig`; any other character finalizes a
  pending `word_buf` into `last_word` and updates `last_sig` (unless whitespace). Every branch that
  consumes a real code character (`"`/`` ` ``/`'` opening a string, `(`, `)`, and the generic
  fall-through) now routes through `_note` instead of managing `last_sig` by hand, so there's one
  update path instead of several that could drift again. While rewriting, caught and fixed a
  second, closely related bug in the same class the reviewer hadn't yet reported: the newline
  branch didn't call `_note` at all, so a keyword split across a line break by itself (`return\n/"/
  ...`, no paren involved) lost the keyword for the *existing* `_JS_REGEX_KEYWORDS` check from
  round 14 too — added a `_note(char)` call there (a `\n` is itself a word-boundary character).
  Verified: the exact `if\n(...)` case and the comment-separated variant both now find the
  hardcode; the analogous `return\n/re/` case (caught by the same self-review, not the external
  one) is also fixed; every same-line paren/keyword regression case from rounds 14–15 stays
  unaffected; the full prior regression table (router identity + all JS/TS cases across every
  round) replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and both changed test files
    against the real repository tree.
- **Seventeenth GitHub PR review round** (repeat review of commit `9a4d935`) — the round-16
  newline/comment regression fix held, but one more JS/TS scanner bypass: entering a block comment
  didn't finalize `word_buf`, so a keyword immediately followed by `/*...*/` and then a regex
  literal (`return/*note*//"/`) still lost the keyword and misclassified the regex as division.
  The user explicitly rejected another one-off patch for this specific branch ("НОРМАЛЬНО ПОПРАВЬ!
  А НЕ КОСТЫЛЬ!") — the right response given the pattern by this point: rounds 15 and 16 each
  patched one more branch that had forgotten to call the shared finalization helper, and this
  finding is a third instance of exactly that same omission (the line-comment-marker branch has
  the identical gap, just not yet reported). Patching the block-comment branch alone would have
  been the fourth iteration of the same narrow fix, not a real fix of the underlying weakness.
  - **Root cause, stated plainly:** finalizing `word_buf` into `last_word` was *opt-in per
    branch* — every branch that consumed a character had to remember to call `_note`/finalize, and
    any branch that didn't (block-comment entry, and structurally also line-comment entry and the
    zero-separator `keyword/regex` case where the `/` decision is made *before* any finalization
    call) silently left `last_word` stale. Three different branches missing the same call across
    three review rounds is a sign the mechanism itself was the problem, not any one branch.
  - **Fix:** restructured `_strip_comments` so identifier characters are handled by one dedicated
    branch at the very top of the "not in an active string/comment" section — the *only* place
    `word_buf` ever grows — and every other character, before any branch-specific logic runs at
    all, passes through one unconditional `_finalize_word()` call. No branch can forget to finalize
    the pending word anymore, because finalization isn't part of any branch's own logic to
    remember; it already happened as a precondition by the time any branch is reached. This closes
    the block-comment case from the review, the line-comment case that hadn't been reported yet,
    and the zero-separator case, all in the same structural change — not three more special cases.
  - **Caught and fixed a self-introduced regression while restructuring, before calling it done:**
    an early draft moved the `\n`-handling branch to *after* the `in_block_comment`/`in_string`
    checks (so it could sit next to the other "word boundary" branches), which broke multi-line
    string/comment line-splitting — a newline consumed while `in_string`/`in_block_comment` was
    active no longer flushed `lines`/`current`, collapsing several physical lines' output into one
    entry and shifting every subsequent line number. Caught by re-running the existing multi-line
    template-literal regression case, not shipped blind. Fixed by keeping `\n` as the first check
    in the loop, exactly as before the restructure (unconditional, ahead of `in_block_comment`/
    `in_string`), and only reordering the *other* branches.
  - Verified: the exact review case (`return/*note*//"/`) now finds the hardcode; a block comment
    separating a keyword from its paren (`if/*x*/(ok) /"/...`) is also fixed; a *multi-line* block
    comment between a keyword and a regex still resolves correctly (and reports the right line
    number); a real identifier followed by a block comment and then real division
    (`foo/*c*//2`) is confirmed to stay division, not a wrongly-skipped regex; the multi-line
    template-literal line-splitting regression case explicitly re-verified line-by-line; the full
    prior regression table (router identity + every JS/TS case across every round) replayed with
    nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Eighteenth GitHub PR review round** (repeat review of commit `8606fcc`) — the round-17
  structural fix held (block-comment/token-finalization thread resolved); one distinct blocking
  gap: keyword recognition is context-blind, so `config.default` (a *property* named `default`,
  valid JS/TS — reserved words are legal property names) makes `last_word == "default"` match
  `_JS_REGEX_KEYWORDS` the same as the real `default` keyword would, misclassifying a following
  real division `/` as a regex start; `_regex_literal_end` then finds the `/` inside a nearby
  `"openai/gpt-4.1"` string as the (fake) regex terminator and strips the `openai/` provider
  prefix off the model hardcode, defeating the guard. Reproduced first (`config.default /
  "openai/gpt-4.1".length` loses the `openai/` prefix from the stripped line).
  - Checked the sibling keyword check (`_JS_CONTROL_KEYWORDS_BEFORE_PAREN`, from round 15) for the
    same shape before fixing anything, since both consult `last_word` against a keyword set the
    identical way: confirmed `obj.if(x) /"/...` (a property named `if`) has the exact same blind
    spot, just not yet externally reported. Fixed both together rather than waiting for a
    predictable next round to report the second one separately.
  - **Fix:** added `last_word_is_property`, tracking whether the current word started
    immediately after a `.` (property access — `config.default`, and `?.` is covered for free
    since the character immediately before the word is still `.` either way). Set at the moment a
    new word starts accumulating (`word_starts_after_dot = last_sig == "."`, captured before
    `last_sig` itself moves on to the word's own first character) and carried into `last_word_is_
    property` when the word is finalized. Both keyword checks (`_JS_REGEX_KEYWORDS`,
    `_JS_CONTROL_KEYWORDS_BEFORE_PAREN`) now additionally require `not last_word_is_property`.
  - Verified: the exact review case (`config.default / "openai/...".length`) now finds the full
    hardcode; the analogous paren case (`obj.if(x) /"/...`) is also fixed — confirmed the `/"/ `
    sequence is preserved unchanged in the stripped output, not wrongly consumed as a regex; a
    genuine `default` keyword (a `switch` statement's `default:` case) before a regex is still
    correctly recognized; optional-chaining property access (`config?.return`) is also excluded
    correctly; every genuine control-keyword and keyword-regex case from prior rounds stays
    unaffected; the full prior regression table (router identity + every JS/TS case across every
    round) replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Nineteenth GitHub PR review round** (repeat review of commit `2cfeec8`) — the round-18
  property-name/keyword blocker is fixed; one distinct blocking gap remains, specific to `.jsx`/
  `.tsx`: a JSX/TSX closing tag (`</div>`, `</>`) starts with `</`, and `<` isn't in
  `_REGEX_PRECEDED_BY_VALUE` (correctly not, for plain `.js`/`.ts`, where `a < /re/` is a real
  comparison-then-regex idiom), so the `/` is misclassified as a regex start; `_regex_literal_end`
  then scans forward and can use the `/` inside a later real `"openai/gpt-4.1"` literal as the
  fake terminator, stripping the `openai/` provider prefix and defeating the guard. Reproduced
  first (`const el = <div></div>; const model = "openai/gpt-4.1";` loses the `openai/` prefix).
  - Checked repo exposure before deciding the fix's shape: 36 real `.jsx`/`.tsx` files exist under
    `SCAN_ROOTS` with real closing tags, and a grep for any `<` immediately followed by a real
    regex literal in those files found none — confirming the fix has real exposure to close and no
    counter-risk to weigh against it.
  - **Fix, scoped correctly rather than broadened past what's justified:** `_strip_comments` gained
    a `jsx: bool = False` parameter (`_regex_offender` passes `path.suffix in (".jsx", ".tsx")`),
    and the regex decision now additionally treats `looks_like_regex` as `False` whenever `jsx` is
    true and `last_sig == "<"` — i.e. `</` never starts a regex literal, but *only* in JSX-capable
    files. Deliberately not applied to plain `.js`/`.ts` (no closing tags can ever appear there,
    and the existing `a < /re/`-is-a-regex behavior — already correct for that file type — stays
    exactly as it was) — broadening it to all JS/TS-family files would have traded a real, rare
    idiom's correctness for a case (JSX closing tags) that structurally cannot occur there.
  - Verified: the exact review case and a JSX fragment closing tag (`</>`) both now find the full
    hardcode; a real regex literal elsewhere in the same JSX file is still correctly recognized as
    one; a real `a < /re/` comparison in a non-JSX (`.ts`) file is confirmed unaffected (still
    treated as a regex, exactly as before this round); the same text with `jsx=True` is confirmed
    to now resolve as division instead (the accepted, checked-safe tradeoff, since this repo has
    no such pattern in any real `.jsx`/`.tsx` file today); `pytest tests/architecture` (24 passed)
    against the real repository tree exercises all 36 real `.jsx`/`.tsx` files with no new false
    positives; the full prior regression table (router identity + every JS/TS case across every
    round) replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Twentieth GitHub PR review round** (repeat review of commit `c81265c`) — the round-19
  JSX-closing-tag fix is confirmed fixed in code (the review notes the closing-tag *thread*
  couldn't be marked resolved because that requires a mutation the user declined to retry, not
  because the fix itself regressed); one distinct blocking gap: the scanner still applies `//`
  JS-comment rules while scanning raw JSX element *text* (the literal content between a tag's `>`
  and the next `<`), which isn't JavaScript at all and has no comment syntax. `const el =
  <div>https://example.com</div>; const model = "openai/gpt-4.1";` truncates at the URL's `//`,
  hiding the real hardcode that follows on the same physical line. Reproduced first.
  - **This finding is qualitatively different from every prior round in this file, and treated
    accordingly.** Every previous JS/TS scanner fix was a *local* character/word-level heuristic
    (one `/`, one preceding keyword, one paren). Correctly distinguishing "inside raw JSX text"
    from "inside a JS expression/statement" requires real nested-structure tracking: an
    opening/closing tag stack, `{...}` expressions embedded in JSX text switching back to JS mode
    and back again, and TSX's well-known `<T>`-generic-vs-JSX-element ambiguity — genuinely
    building a second hand-rolled parser, the exact failure mode that already justified moving
    Python/YAML onto real parsers in round 10, and exactly the ceiling this file's own decision
    log already named for the JS/TS path ("no dependency-free JS/TS tokenizer available").
  - **Fix, chosen deliberately over building that tracker:** disable `//` line-comment recognition
    entirely for JSX-capable files (`.jsx`/`.tsx`), keeping block-comment and regex-literal
    recognition unaffected (neither is implicated by this finding). This is the *conservative*
    direction for a boundary guard, not a shortcut: it can only ever cause the scanner to
    *include* more content in scanning (a real inline `//` comment's text, now also checked
    against the model-string regex) — never exclude content that should have been checked. A false
    positive here costs a human one look at one line; a false negative is exactly the silent
    boundary bypass this whole test exists to prevent. Implemented by excluding `"//"` from the
    markers considered in the line-comment branch specifically when `jsx` is true — `.js`/`.ts`
    (which can never contain JSX and where `//` unambiguously always means a real comment) are
    completely unaffected.
  - Verified: the exact review case now finds the full hardcode; block comments and the round-19
    closing-tag regex fix both still work correctly in JSX files; a genuine `//` comment in a JSX
    file is confirmed to no longer truncate the rest of the line (its content is now scanned
    instead, the accepted false-positive-safe direction); `.ts` (non-JSX) `//` truncation is
    confirmed completely unaffected; `pytest tests/architecture` (24 passed) against the real
    repository tree exercises all real `.jsx`/`.tsx` files with no new false positives from any
    real inline comment; the full prior regression table (router identity + every JS/TS case
    across every round) replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Twenty-first GitHub PR review round** (repeat review of commit `ddc1c136`) — round 20's
  raw-JSX-URL false negative is fixed, but the review found round 20's own fix was itself flawed
  and introduced a *worse* bypass: `const el = <div />; // /* note\nconst model =
  "openai/gpt-4.1";` — a genuine `//` comment whose *text* happens to contain `/*` — lost the
  entire rest of the file, not just one line.
  - **Root cause, stated plainly:** round 20 excluded `"//"` from the markers the line-comment
    branch considered, but didn't stop the *rest* of the character-by-character scan from running
    over the comment's own text as if it were code. "Not a truncation point" was implemented as
    "fall through to the ordinary lexer", which is a different (and wrong) thing: the comment's
    two slashes themselves got consumed as a fake empty regex literal (`_regex_literal_end` found
    the second `/` as the "closing" one immediately), then the `/*` inside the comment's own prose
    opened a *real* `in_block_comment` state with no matching `*/` anywhere in the file to ever
    close it — silently swallowing everything after it, a strictly worse failure than the bug
    round 20 was fixing. Reproduced first, exactly as reported.
  - **Fix:** added a genuine `in_line_comment` state (reset every `\n`, since a `//` comment never
    spans a line) entered only when `jsx` is true and `//` is found outside any existing
    string/comment. While in this state, every character is appended to `current` verbatim through
    exactly one branch, with no other lexer logic (no quote/regex/block-comment recognition)
    running over it at all — the comment's own content stays available for the model-string regex
    to match against (preserving round 20's actual goal), but cannot mutate lexer state for
    anything that follows it, closing the exact class of bug the review named. For `.js`/`.ts`
    (`jsx` false), `//` is never intercepted by this new branch and falls through unchanged to the
    original marker-based truncation — completely unaffected by this round.
  - Verified: the exact review reproduction now finds the hardcode on the following line instead
    of losing the rest of the file; the round-20 raw-JSX-URL case is still fixed; a genuine `//`
    comment's content is still scanned instead of truncated (round 20's actual intent, now
    implemented safely); additional stress cases — an unterminated quote inside a `//` comment,
    and two separate genuine `//` comments across two lines — both confirmed not to corrupt state
    for what follows; block comments, the round-19 closing-tag fix, and real regex literals all
    still work correctly in JSX files; `.ts` (non-JSX) `//` truncation is confirmed completely
    unaffected; `pytest tests/architecture` (24 passed) against the real repository tree exercises
    every real `.jsx`/`.tsx` file's actual comments with no new false positives or silent losses;
    the full prior regression table (router identity + every JS/TS case across every round)
    replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Twenty-second GitHub PR review round** (repeat review of commit `669f7446`) — the round-21
  `// /*` state-leak fix is confirmed fixed; one more, symmetric blocking gap: raw JSX text can
  contain `/*` literally (`<pre>Use /* to start a comment</pre>`), which has no comment semantics
  there (only inside a JS expression like `{/* comment */}` does it), but the scanner still
  unconditionally opened a real `in_block_comment` state with no guaranteed closing `*/`,
  swallowing the rest of the file. Reproduced first, exactly as reported.
  - **Fix, applying the round-21 lesson from the start this time:** for `jsx == True`, `/*` is now
    intercepted before it can open `in_block_comment` and its two characters are appended as
    ordinary, non-comment text — mirroring the `//` fix's actual intent (never remove content that
    might contain a hardcode) without repeating round 20's mistake (letting the content drive the
    stateful lexer as if it were code). `last_sig` is deliberately set to bias a *following* `/`
    toward "division/ordinary text" rather than "regex start", since raw JSX prose can easily
    contain an unrelated `/` later on the line that must not be misread as that literal's closing
    delimiter.
  - **Caught a second, self-introduced bug from this same fix before calling it done, via the
    established regression suite, not a fresh review round:** a genuine block comment in a JSX
    file (`/* real comment */`) now has its own content pass through as ordinary characters too —
    including its closing `*/`, whose `/` was then itself misread as *opening a new fake regex*,
    consuming forward to the next unrelated `/` on the line (in the test case, straight through a
    real `"openai/gpt-4.1"` hardcode). Fixed by adding one more jsx-scoped exclusion to the
    regex-vs-division decision: a `/` immediately preceded by `*` is never treated as a regex
    start when `jsx` is true (mirroring the existing `<` exclusion from round 19) — `a * /re/` is
    not a pattern this repo uses anywhere, so this carries no practical cost even though it's a
    small further narrowing of the regex heuristic specifically for JSX-capable files.
  - Verified: the exact review case now finds the hardcode; a raw-JSX-text `/*` followed by an
    unrelated later `/` on the same line no longer consumes forward into real content; a genuine
    block comment's content is still scanned (not silently lost, and no longer corrupted by its
    own closing `*/`); the round-19 closing-tag fix, the round-20/21 `//`-comment fixes, and real
    regex-literal recognition all still work correctly in JSX files; `.ts`/`.js` (non-JSX) block
    comments are confirmed completely unaffected; `pytest tests/architecture` (24 passed) against
    the real repository tree exercises every real `.jsx`/`.tsx` file's actual block comments with
    no new false positives or silent losses; the full prior regression table (router identity +
    every JS/TS case across every round) replayed with nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
    against the real repository tree.
- **Twenty-third GitHub PR review round** (repeat review of commit `9ab4c764`) — the round-22
  raw-JSX-`/*` fix confirmed fixed; one more blocking gap, but this time the review's own diagnosis
  named the *pattern*, not just an instance: a plain `/` starting ordinary raw JSX text
  (`<div>/docs {"openai/gpt-4.1"}</div>` — `>` isn't a value character, so `/docs` looks like a
  regex start) still gets skipped via `_regex_literal_end`, whose "closing" delimiter can be a real
  hardcode's own separator — not a real regex boundary at all. The review stated plainly: special-
  casing `</`, `//`, `/*`, `*/` closes individual examples one at a time, but the scanner still
  applies JS regex semantics while actually in raw JSX text, and asked for either real JSX/TS
  parsing or a conservative policy that never removes source ranges when JSX context is unknown.
  Reproduced first, exactly as reported.
  - **This round closes the class, not one more instance.** Every prior JSX fix (rounds 19–22)
    recognized one *specific shape* that shouldn't have been treated as a regex/comment at all
    (`</`, a `//` comment, `/*` text, a `*/` closer) and excluded that shape from being detected as
    such. This finding shows that approach can't be complete by enumeration — any `/`-then-later-`/`
    pair in raw JSX text can be misdetected as a regex, regardless of what precedes it, because the
    underlying ambiguity (is this really a regex, or just two unrelated slashes in rendered text?)
    is undecidable from character context alone. Taking the review's own conservative option: for
    `jsx == True`, when the heuristic (rightly or wrongly) decides a span looks like a regex
    literal and finds a "closing" `/`, the span's characters are now kept in `current` (appended
    verbatim) instead of being skipped past and discarded — so *even when the detection is wrong*,
    no content is ever lost. The quote-corruption risk that originally motivated skipping regex
    content in the first place (a quote inside a real regex opening a bogus `in_string`) stays
    fully protected, since the span is still recognized and its characters still bypass the normal
    quote-opening logic — only the *discarding* is removed, not the detection itself. `.js`/`.ts`
    keep discarding real regex-literal content exactly as before (a regex pattern's own source text
    isn't somewhere a real hardcode is expected to live, and the existing, heavily-regression-tested
    detection behavior for those file types depends on that content being absent from the stripped
    line) — scoped to `jsx` only, matching every other JSX-specific narrowing in this file.
  - Verified: the exact review case now finds the full hardcode; a genuine JS regex literal in a
    non-JSX `.ts` file still has its content excluded exactly as before (unaffected); a real regex
    literal in a JSX file (`/simplepattern/`) no longer discards its own surrounding content but
    also doesn't false-positive on itself; the original quote-inside-a-regex protection (`/"/`) is
    confirmed intact in JSX files with no corruption; every prior round's fix (18 through 22) stays
    unaffected; `pytest tests/architecture` (24 passed) against the real repository tree exercises
    every real regex literal in every real JS/TS/JSX/TSX file with no new false positives; the full
    prior regression table (router identity + every JS/TS case across every round) replayed with
    nothing flipped.
  - Re-ran the full `pytest tests/architecture` suite (24 passed) and the changed test file
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
- [x] Reproduced both round-14 findings with standalone scripts against current code before
      changing anything: `from . import shared; shared.router.get(...)` still resolved to no
      literals at all; a keyword-preceded regex (`return /"/`) still truncated a real hardcode the
      same way the round-12 finding did.
- [x] Manual check: the exact `from . import shared` case now resolves; `from .. import shared`
      (two levels, correctly placed one package up) resolves against the correct target; `from .
      import name` where `name` is a plain name bound in `__init__.py` (not a submodule file)
      still resolves via the pre-existing mechanism; a control case (`from . import utils`, not a
      router) stays clean.
- [x] Manual check: the exact `return /"/` case now finds the hardcode; `typeof`/`instanceof`/
      `case`-preceded regexes are also caught; an identifier merely *named* `returned` (not the
      keyword `return`) still divides correctly, confirming word-boundary matching, not substring
      matching; all prior JS/TS regression cases (operator-preceded regex, escaped-slash regex,
      character-class regex, plain division) stay unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), both changed files against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.
- [x] Reproduced both round-15 findings with standalone scripts against current code before
      changing anything: `from anytoolai_platform_api.routers import demo; demo.router.get(...)`
      still resolved to no literals at all; `if (ok) /"/.test(input)` still truncated a real
      hardcode the same way every prior round's finding in this file did.
- [x] Manual check: the exact absolute `from package import submodule` case now resolves; a
      qualified-relative variant (`from .routers import demo`) resolves; the real `main.py`
      pattern (`from pkg.routers.demo import router as demo_router`) is explicitly confirmed
      unaffected — the one regression risk worth checking given how broad this fix is; a control
      case (an absolute submodule import that isn't a router) stays clean.
- [x] Manual check: the exact `if (ok) /"/...` case now finds the hardcode; `while`/`switch`-
      condition variants are also caught; a real function-call paren still divides correctly
      (`foo(1) / 2`); a real call inside a condition body still divides correctly after the
      condition closes; nested parens resolve the stack correctly; all prior regression cases
      (keyword-preceded regex, operator-preceded regex, escaped-slash/character-class regex,
      plain division, backtick, block comments) stay unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), both changed files against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.
- [x] Reproduced the round-16 finding with a standalone script against current code before
      changing anything: `if\n(ok) /"/.test(input); ...; const model = "openai/gpt-4.1";` still
      truncated the real hardcode once `if` was split onto its own line; a comment-separated
      variant (`if // note\n(ok) ...`) reproduced identically.
- [x] Manual check: the exact `if\n(...)` and comment-separated cases now find the hardcode; an
      analogous `return\n/re/` case (a second bug in the same class, found via self-review before
      it was externally reported) is also fixed; every same-line paren/keyword regression case
      from rounds 14–15 stays unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), both changed files against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.
- [x] Reproduced the round-17 finding with a standalone script against current code before
      changing anything: `function f(){ return/*note*//"/; } ...; const model =
      "openai/gpt-4.1";` still truncated the real hardcode; also independently confirmed the
      zero-separator sibling case (`return/"/.test(x); ...`) was broken the same way, before
      deciding to fix the mechanism rather than the one reported branch.
- [x] Manual check: the exact review case, a block comment separating a keyword from its paren,
      and a *multi-line* block comment between a keyword and a regex all now resolve correctly
      (including correct line numbers); a real identifier followed by a block comment and then
      real division is confirmed to stay division, not a wrongly-skipped regex.
- [x] Caught, during the restructure itself (before declaring it done), a self-introduced
      regression from reordering the `\n` branch: multi-line string/comment line-splitting broke
      (a newline inside an active string/comment stopped flushing `lines`, collapsing several
      physical lines into one and shifting every later line number). Fixed by keeping `\n` as the
      unconditional first check in the loop, exactly as before the restructure; explicitly
      re-verified the multi-line template-literal case line-by-line after the fix.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), the changed file against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.
- [x] Reproduced the round-18 finding with a standalone script against current code before
      changing anything: `config.default / "openai/gpt-4.1".length` stripped the `openai/`
      provider prefix off the model literal. Also independently reproduced the analogous
      not-yet-reported paren case (`obj.if(x) /"/...`) before deciding to fix both together.
- [x] Manual check: the exact review case and the analogous paren case both now leave the real
      hardcode/regex content intact; a genuine `default` keyword (`switch` statement) before a
      regex, and a genuine control keyword before a paren, are both still correctly recognized;
      optional-chaining property access (`config?.return`) is also correctly excluded; every prior
      keyword-regex/control-paren regression case stays unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed), the changed file against the real
      repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed)
      all green after this round.
- [x] Reproduced the round-19 finding with a standalone script against current code before
      changing anything: `const el = <div></div>; const model = "openai/gpt-4.1";` stripped the
      `openai/` prefix off the model literal. Checked repo exposure first: 36 real `.jsx`/`.tsx`
      files with real closing tags exist under `SCAN_ROOTS`, and none contain a `<` immediately
      followed by a real regex literal (confirming the fix has real exposure and no counter-risk).
- [x] Manual check: the exact review case and a JSX fragment closing tag (`</>`) both now leave
      the hardcode intact; a real regex literal elsewhere in the same JSX file is still correctly
      recognized; a real `a < /re/` comparison in a non-JSX (`.ts`) file is confirmed unaffected —
      still resolves as a regex exactly as before this round, since `jsx` scopes the exclusion to
      `.jsx`/`.tsx` only.
- [x] `python3 -m pytest tests/architecture -q` (24 passed, exercising all 36 real `.jsx`/`.tsx`
      files with no new false positives), the changed file against the real repository tree,
      `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) all green after
      this round.
- [x] Reproduced the round-20 finding with a standalone script against current code before
      changing anything: `const el = <div>https://example.com</div>; const model =
      "openai/gpt-4.1";` truncated at the URL's `//`, hiding the real hardcode.
- [x] Manual check: the exact review case now finds the full hardcode; block comments and the
      round-19 closing-tag regex fix both still work in JSX files; a genuine `//` comment in a JSX
      file is confirmed to no longer truncate (its content is scanned instead — the accepted,
      false-positive-safe direction); `.ts` (non-JSX) `//` truncation is confirmed completely
      unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed, exercising all real `.jsx`/`.tsx`
      files with no new false positives from any real inline comment), the changed file against
      the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check`
      (981 passed) all green after this round.
- [x] Reproduced the round-21 finding with a standalone script against current code before
      changing anything: `const el = <div />; // /* note\nconst model = "openai/gpt-4.1";` lost
      the entire second line, not just the comment's own line — confirming round 20's fix was
      itself flawed, not just incomplete.
- [x] Manual check: the exact review reproduction now finds the hardcode on the line after the
      comment; the round-20 raw-JSX-URL case is still fixed; a genuine `//` comment's content is
      still scanned instead of truncated; an unterminated quote inside a `//` comment and two
      separate genuine `//` comments across two lines are both confirmed not to corrupt state for
      what follows; block comments, the round-19 closing-tag fix, and real regex literals all
      still work in JSX files; `.ts` (non-JSX) `//` truncation is confirmed completely unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed, exercising every real `.jsx`/`.tsx`
      file's actual comments with no new false positives or silent losses), the changed file
      against the real repository tree, `validate_architecture.py`, `validate-docs`, and
      `quick-check` (981 passed) all green after this round.
- [x] Reproduced the round-22 finding with a standalone script against current code before
      changing anything: `const el = <pre>Use /* to start a comment</pre>;\nconst model =
      "openai/gpt-4.1";` lost the rest of the file the same way round 21's `//` finding did.
- [x] Caught a second, self-introduced bug from this same fix via the established regression
      suite before calling it done (not from a fresh review round): a genuine block comment's own
      closing `*/` had its `/` misread as opening a fake regex, consuming forward through a real
      hardcode on the same line. Fixed by excluding a `/` preceded by `*` from the regex decision
      when `jsx` is true.
- [x] Manual check: the exact review case and a raw-JSX-text `/*` followed by an unrelated later
      `/` on the same line both now leave the hardcode intact; a genuine block comment's content
      is scanned correctly (not lost, not corrupted by its own `*/`); the round-19/20/21 fixes and
      real regex-literal recognition all still work in JSX files; `.ts`/`.js` block comments are
      confirmed completely unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed, exercising every real `.jsx`/`.tsx`
      file's actual block comments with no new false positives or silent losses), the changed file
      against the real repository tree, `validate_architecture.py`, `validate-docs`, and
      `quick-check` (981 passed) all green after this round.
- [x] Reproduced the round-23 finding with a standalone script against current code before
      changing anything: `const el = <div>/docs {"openai/gpt-4.1"}</div>;` — a plain `/` starting
      raw JSX text, misdetected as a regex — dropped the `openai/` prefix from the stripped line.
- [x] Manual check: the exact review case now finds the full hardcode; a genuine JS regex literal
      in a non-JSX `.ts` file still has its content excluded exactly as before; a real regex
      literal in a JSX file no longer discards its surrounding content but doesn't false-positive
      on itself; the original quote-inside-a-regex protection is confirmed intact in JSX files
      with no corruption; every prior round's fix (18 through 22) stays unaffected.
- [x] `python3 -m pytest tests/architecture -q` (24 passed, exercising every real regex literal
      in every real JS/TS/JSX/TSX file with no new false positives), the changed file against the
      real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check`
      (981 passed) all green after this round.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-31 | "No product-specific endpoints" test asserts against a forbidden-term list on known router files' route/prefix literals, not a general "every path is `{product_id}`-parameterized" proof. | FastAPI routes can be parameterized several ways; a general proof is brittle and over-engineered for 7 router files. Matches the existing forbidden-term-list style already used by `test_no_freelancer_terms_in_platform_core.py`. |
| 2026-08-31 | LiteLLM-model-string test scans production source only (`apps/`, `packages/`, `extensions/`, `configs/`, excluding `tests/`), not test fixtures. | Tests legitimately assert against the real config values (e.g. `test_litellm_adapter.py` asserting `response.model == "openai/gpt-4.1-mini"`); flagging those would be a false positive, not a real boundary violation. |
| 2026-09-01 | Superseded by the next entry: round 24 initially left `test_no_direct_provider_calls_outside_gateway.py` (JS/TS provider-package/raw-HTTP-host enforcement) and `test_no_prompts_inside_extensions.py` (structural system-role message-shape detection) unfixed, reasoning that both files predate and aren't touched by this PR's diff. | Round 25 ("Code-review (me #17)") escalated this as blocking and, on reflection, correctly: the ticket's own AC/implementation-notes explicitly require auditing "no prompts in extensions" and "no direct provider calls outside gateway" regardless of which file implements the check — whether a gap sits in a pre-existing file is irrelevant to whether the audit's own stated boundary is actually enforced. Reversed; see the round-25 entry below. The temp-tree-regression-fixture ask remains deferred as genuinely non-blocking. |
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
| 2026-08-31 | Bare `import X.Y.Z` (no `as`) and `from . import name` are explicitly left unhandled by the module-alias fix, documented in `_module_import_aliases`'s docstring rather than silently missing. | Bare `import X.Y.Z` binds only the top-level package name in Python's own semantics, needing multi-level attribute-chain resolution (`X.Y.Z.router`, not just `Y.router`) to close correctly; `from . import name` is statically ambiguous between "a submodule named `name`" and "a name defined in `__init__.py`" without also consulting the filesystem. Neither is used anywhere in this repo today (verified) — the same "don't build for a pattern that hasn't been shown to exist" call already made for star imports and cross-module constant resolution in the round-11 decision log. **Superseded by round 14, `from . import name` half**: escalated as a blocker regardless of current non-use — see below. The bare-`import X.Y.Z`-without-`as` half stands. |
| 2026-08-31 | The JS/TS regex-vs-division ambiguity is resolved with the standard last-*character* lexer heuristic (`_REGEX_PRECEDED_BY_VALUE`/`_regex_literal_end`), not a full JS/TS tokenizer, and the resulting keyword-preceded-regex gap (`return /re/`) is documented rather than closed. | This is the third finding against the hand-rolled JS/TS scanner specifically (round 3's backtick strings, round 11's block comments, this regex-literal gap) — the same repeat-failure pattern that already justified moving Python/YAML onto real parsers in round 10 — but unlike Python (`tokenize`) and YAML (already-a-dependency PyYAML), no stdlib or already-a-dependency JS/TS tokenizer exists to switch to without adding a new dependency, so the round-10 "known, narrower ceiling, accepted" tradeoff for this path stands. The character-level heuristic closes the concretely reported case (and the operator/punctuation-preceded cases that are the vast majority of real regex literals) for the cost of a bounded, well-known lexer trick instead of a full parser; the keyword-preceded case it can't distinguish (a keyword and an identifier can end in the same character) was checked against all 142 real `.js`/`.ts`-family files this test scans and confirmed absent today, so closing it now would be exactly the "build for a pattern that hasn't been shown to exist" scope-creep this round's own sibling decision (bare imports, above) argues against. **Superseded by round 14**: escalated as a blocker regardless of current non-use — see below. |
| 2026-08-31 | `from . import shared`/`from .. import shared` is now resolved as a module-identity source when a submodule file actually named `shared` exists (checked via `module_paths`), rather than staying an explicit gap. | The round-13 "not used anywhere in this repo today" justification doesn't survive an explicit escalation calling it a blocker regardless of current usage — a review verifying the same code twice and treating a documented gap as still-live is itself evidence the gap is real, not evidence to keep arguing scope. The filesystem check (does `<container>.<name>` match a real file in `module_paths`?) is exactly the missing static signal that made this "ambiguous" before — it isn't ambiguous once the file tree is already fully parsed and available, which it is here. **Superseded by round 15**: the `node.module is None and node.level > 0` restriction that scoped this fix to only the *bare relative* form was itself an unjustified narrowing — see below. |
| 2026-08-31 | The keyword-preceded regex-literal gap is closed with `_JS_REGEX_KEYWORDS` (a small fixed keyword set) plus `_last_word` (word-level, not char-level, lookback), rather than left as a documented ceiling. | Same reasoning as the `from . import shared` reversal above — escalated as a blocker regardless of current non-use. A fixed keyword set is a bounded addition (no new dependency, no full tokenizer) that only ever makes the heuristic *more* permissive toward detecting a regex (a real identifier, even one that shares a prefix with a keyword like `returned`, never matches the set), so it carries no new false-positive risk to weigh against closing the gap. |
| 2026-08-31 | `_module_import_aliases`'s submodule-file check now runs for every `ast.ImportFrom` (relative or absolute), not gated on `node.module is None and node.level > 0`. | Round 14's fix matched only the *literal shape* of that round's reported example (`from . import shared`), when the actual determining question — "does `<container>.<name>` match a real submodule file in `module_paths`?" — never depended on whether the import was relative or absolute; the restriction was copied from the review's example rather than derived from the logic, and round 15's absolute-import finding is the direct, predictable consequence. Explicitly verified the one real regression risk this broadening carries — the repo's own dominant pattern, `from anytoolai_platform_api.routers.demo import router as demo_router` — stays correctly unaffected (`router` isn't a submodule of `demo`, so the check still falls through to the pre-existing name-edge mechanism for it). |
| 2026-08-31 | The JS/TS regex-vs-division heuristic gains paren-structure tracking (`paren_stack`, `_JS_CONTROL_KEYWORDS_BEFORE_PAREN`) so a control-flow condition's closing paren clears `last_sig` instead of marking it a value, rather than leaving `)` universally value-like. | `if (cond) /re/` is a real, common JS/TS idiom (a regex literal in statement position right after a condition) that a receiver-blind `)`-is-always-a-value rule can't get right — the paren that closes a *condition* isn't the same kind of `)` as the paren that closes a *function call*, and only tracking what opened the matching `(` (a keyword vs. anything else) distinguishes them. This is scoped to the smallest structural addition that closes the reported case: it does not attempt to model arrow functions, destructuring, or any other paren-adjacent JS/TS construct not shown broken. **Superseded by round 16**: the keyword lookup this depended on (`_last_word(current)`) was itself line-scoped while `last_sig` persists across lines — see below. |
| 2026-08-31 | `_last_word(chars)` (a lazy, line-scoped read of `current`) is replaced with a persistent `word_buf`/`last_word` pair, updated incrementally alongside `last_sig` through one shared `_note(char)` closure, rather than kept as a per-call computation. | `current` (the stripped-line accumulator) resets at every physical line by design (each line is reported independently), but `last_sig` is deliberately *not* reset at newlines (that's what lets quote/comment state survive a line break in the first place) — a keyword or a control-flow `(` legitimately separated from what follows it by a line break or a comment (`if\n(cond)`, `return\n/re/`) made `_last_word(current)` silently return "" exactly when it mattered, because it was reading from the wrong-lifetime buffer. This is the same "two independently-updated copies of one state machine drift apart" failure this file's own decision log has already named three times (`SKIP_PATH_PARTS`, `_TRIPLE_QUOTES`, the receiver/alias checks) — the fix is the same each time: one shared update path instead of two. |
| 2026-08-31 | The newline branch in `_strip_comments` now calls `_note("\n")` before resetting `current`, treating a line break as a word-boundary character. | Found via self-review while implementing the `_last_word` replacement above, not from an external report: without this, `word_buf` never gets finalized into `last_word` when a keyword is immediately followed by a bare newline with nothing else on that physical line (`return\n/re/`) — the *existing* round-14 `_JS_REGEX_KEYWORDS` check has the identical bug the round-16 review reported for the paren case, just without a paren in the way. Fixing the shared root cause (persistent `last_word` tracking) closes both instances at once; this decision records that the newline call site needed the same treatment as every other character-consuming branch, not a separate mechanism. **Superseded by round 17**: per-branch opt-in finalization (`_note`, called from each character-consuming branch individually) was itself the weakness — a fourth branch (block-comment entry) turned up missing the same call; see below. |
| 2026-08-31 | Per-branch `_note(char)` calls (one per character-consuming branch: string-open, `(`, `)`, generic fall-through, newline) are replaced with a structural split: one dedicated branch handles every identifier character (the only place `word_buf` grows), and one unconditional `_finalize_word()` call runs for every other character before any branch-specific logic sees it — rather than adding a fifth `_note`/finalize call to the block-comment-entry branch the round-17 review reported missing one. | Three review rounds in a row (15, 16, 17) each found a *different* branch that had forgotten to call the shared finalization helper (a paren branch, the newline branch, now block-comment entry) — the same helper existing didn't stop the omission, because calling it was still each branch's own responsibility to remember. The user explicitly rejected patching the fourth instance the same way ("НОРМАЛЬНО ПОПРАВЬ! А НЕ КОСТЫЛЬ!"): making finalization a structural precondition instead of a per-branch opt-in makes the *whole class* of "this branch forgot to flush the word" bug impossible by construction, closing the reported block-comment case, the not-yet-reported line-comment case, and the zero-separator case in one change instead of three more narrow patches. |
| 2026-08-31 | The `\n`-handling branch stays the unconditional first check in `_strip_comments`'s loop (ahead of `in_block_comment`/`in_string`), not folded into the new "every non-identifier character" tail alongside the other word-boundary branches. | Caught via self-review, not shipped: an intermediate version of the round-17 restructure moved `\n` handling next to the other boundary branches (after the `in_block_comment`/`in_string` checks), which broke multi-line string/comment line-splitting — a newline consumed while inside an active string or block comment stopped flushing `lines`/`current`, collapsing several physical lines' output into one entry and shifting every later line number. `\n` is not like the other boundary characters here: it must end a physical line's output *regardless* of lexical state (`in_string`/`in_block_comment` persist across the split, but the split itself must still happen), which only holds if it's checked before those states get a chance to consume it. |
| 2026-09-01 | Both keyword-matching checks (`_JS_REGEX_KEYWORDS`, `_JS_CONTROL_KEYWORDS_BEFORE_PAREN`) now also require `not last_word_is_property`, tracked via a new `word_starts_after_dot`/`last_word_is_property` pair set at the moment a word starts accumulating (was the char immediately before it a `.`?), rather than matching `last_word` against the keyword set on spelling alone. | Reserved words are valid JS/TS property names (`config.default`, `obj.if`), so an IdentifierName spelled like a keyword right after `.`/`?.` is a real property access, not a keyword token — matching on spelling alone treated `config.default` and the actual `default` keyword identically, letting a following real division be misclassified as a regex start. Checked the sibling paren-keyword check for the identical shape *before* fixing anything (given the established pattern of these two checks sharing bugs — round 16 fixed both symmetric branches together too) and found it broken the same way (`obj.if(x)`), not yet externally reported; fixed both together rather than waiting for a predictable next round to report the second one separately. |
| 2026-09-01 | `_strip_comments` gains a `jsx: bool = False` parameter that excludes `<` from qualifying as "not a value" (so `</` never starts a regex) only when true; `_regex_offender` passes `path.suffix in (".jsx", ".tsx")`, not applied to plain `.js`/`.ts`. | A JSX/TSX closing tag (`</div>`, `</>`) starts with `</`, and `<` is correctly *not* in `_REGEX_PRECEDED_BY_VALUE` for plain JS/TS (`a < /re/` is a real comparison-then-regex idiom there) — so the ambiguity is genuinely file-type-dependent, not a single universal rule to fix. Checked repo exposure before choosing the fix's shape: 36 real `.jsx`/`.tsx` files exist with real closing tags (real exposure to close) and none contain a `<` immediately followed by a real regex literal in any scanned file, `.jsx`/`.tsx` included (no counter-risk from also narrowing `.jsx`/`.tsx`'s own `a < /re/` case, though the fix doesn't even need to rely on that — it only ever changes behavior when `last_sig == "<"` specifically, i.e. `</`, not a bare `<` followed by whitespace then a regex). |
| 2026-09-01 | `//` line-comment recognition is disabled entirely for JSX-capable files (`jsx == True`), rather than attempting to track "currently inside raw JSX text" vs. "currently inside a JS expression/statement" with a hand-rolled nested-tag/expression state machine. | Correctly distinguishing JSX element text (no comment syntax at all) from JS code requires real nested-structure tracking — opening/closing tag matching, `{...}` expressions switching back to JS mode and back again, and TSX's `<T>`-generic-vs-JSX-element ambiguity — which is genuinely building a second hand-rolled parser, the exact class of approximation that already justified moving Python/YAML onto real parsers in round 10 and that this file's own decision log already named as this path's accepted ceiling ("no dependency-free JS/TS tokenizer available"). Disabling `//` recognition is the direction that matches this test's actual purpose (a boundary *guard*, not a linter): it can only ever make the scanner check *more* content, never less — a real inline comment's text is now also checked against the model-string regex (occasional false positive, a human looks at one line) instead of the alternative failure mode (a real hardcode silently truncated and missed, which is exactly what this test exists to prevent). Block comments and regex-literal recognition are unaffected — neither is implicated by this finding, and narrowing further than what's demonstrated broken would be the same unjustified scope-creep already rejected elsewhere in this file's decision log. **Superseded by round 21**: "disabled" was implemented as "excluded from the marker check", which let the comment's own text fall through to the *ordinary* character-by-character lexer instead of being consumed as inert — a real correctness bug in the fix itself, not just an incomplete one. See below. |
| 2026-09-01 | A genuine `in_line_comment` state (reset every `\n`) replaces the round-20 "exclude `//` from markers" approach: while in this state, every character is appended to `current` through exactly one branch, with no other lexer branch (quote/regex/block-comment recognition) ever running over it. | "Not a truncation point" is not the same claim as "safe to feed through the same stateful lexer that parses real code" — round 20's fix let a `//` comment's own prose (e.g. containing `/*`) open a *real* `in_block_comment` state with no matching `*/` anywhere in the file, silently swallowing everything after it, a strictly worse bug than the truncation round 20 was fixing. Comment text needs to stay *available* for the model-string regex (round 20's actual, correct goal) while being structurally *inert* to every other lexer branch — a dedicated, verbatim-consuming state is the only way to get both at once, the same "one shared mechanism, not several independently-behaving branches" lesson this file's decision log has already drawn multiple times for other parts of this same scanner. |
| 2026-09-01 | `/*` in a JSX-capable file is treated as two ordinary, non-comment characters (never opens `in_block_comment`), applying the round-21 lesson from the start rather than repeating round 20's original mistake of letting the content fall through unguarded to the rest of the lexer. | Raw JSX text can contain `/*` literally with no comment semantics at all (only inside a JS expression like `{/* comment */}` does it mean anything), and unconditionally opening `in_block_comment` for it has no guaranteed closing `*/` in JSX text — the same "state leaks past this point, swallowing the rest of the file" failure round 21 already fixed for `//`, just via `/*` instead. Unlike `//` (which naturally ends at the next `\n`, giving `in_line_comment` a clean exit condition), raw JSX text has no reliable end marker a character-level heuristic can find without the full JSX-nesting tracker this file has already declined to build (round 20) — so `/*` gets the "treat as ordinary text" version of the fix rather than a dedicated consuming state, deliberately paired with the sibling decision below to close the gap that choice opens. |
| 2026-09-01 | A `/` immediately preceded by `*` is excluded from the regex-vs-division decision when `jsx` is true (mirroring the existing `<` exclusion from round 19), scoped to JSX-capable files only. | Self-caught, not externally reported: treating `/*` as ordinary text (the decision above) means a genuine block comment's own closing `*/` now also passes through as ordinary characters, and its `/` was then itself misread as *opening a new fake regex*, consuming forward to the next unrelated `/` on the same line — including through a real hardcode, in the exact regression case this surfaced in. `a * /re/` (a real division immediately followed by a regex literal) is not a pattern this repo uses anywhere, so excluding it for JSX-capable files carries no practical cost; scoping to `jsx` only (rather than universally) keeps `.js`/`.ts` behavior for that already-rare idiom completely unchanged, consistent with every other JSX-specific narrowing in this file. |
| 2026-09-01 | For `jsx == True`, a span the regex-vs-division heuristic decides "looks like a regex" is no longer discarded when skipped past — its characters are appended verbatim to `current` instead, closing the *class* of "misdetected regex silently eats real content" rather than one more enumerated shape (`</`, `//`, `/*`, `*/`) of it. `.js`/`.ts` keep discarding real regex-literal content exactly as before. | Every prior JSX fix in this file (rounds 19–22) recognized one specific character sequence that shouldn't have been treated as a regex/comment and excluded that shape from detection — but a plain `/word` in raw JSX text (`<div>/docs {"openai/gpt-4.1"}</div>`) shows the underlying ambiguity (is a `/`-bounded span really a regex, or two unrelated slashes in rendered text?) is undecidable from character context alone, so enumeration can never be complete. The review's own suggested conservative policy — never remove a source range based on a regex-literal heuristic when JSX context is unknown — is implemented literally: the span is still *recognized* (so a quote inside it still can't corrupt `in_string` state, preserving the original reason regex-skipping existed at all) but never *discarded*, so a misdetection can no longer lose real content regardless of what shape it takes. Scoped to `jsx` rather than applied universally because `.js`/`.ts`'s existing, heavily-regression-tested detection behavior already depends on real regex-literal pattern text being absent from the stripped line — a change with no reported problem in that file type and a real risk of disturbing 20+ rounds of established regression coverage for no benefit. |

| 2026-09-01 | One shared static string resolver (`tests/architecture/static_string_resolution.py`) replaces the four per-gate ad-hoc resolvers; every gate exposes a `check_*(root, ...)` function and carries isolated `tmp_path` regressions. | Round 34's four findings (an f-string/template of a known constant in the LiteLLM gate, a concatenated provider host, a constant-indirected `role`/instruction payload in an extension, a route path imported from another module) were four instances of one root cause: each gate answered "which string can this expression statically take?" separately, so every fold added to one (round 30's concat, round 32/33's f-string) stayed missing from the rest, and the next round found the same hole one gate over — the exact whack-a-mole pattern this log has recorded since round 24. Folding once, for all gates, is the smaller total diff *and* the only shape where a closed gap stays closed everywhere. `check_*(root)` functions were the natural byproduct: they're what lets a fixture tree under `tmp_path` run the real gate (skip-dir filtering now applies to `root`-relative parts, so `/tmp` no longer disqualifies a fixture), which also landed round 24's deferred permanent-regression ask. `iter_source_files` prunes with `os.walk` instead of `rglob` (1.1M entries under `node_modules`/`.venv` were walked per call): the architecture suite dropped from 54s to ~3s. |

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
| 2026-08-31 | Fourteenth GitHub PR #96 review round (reviewing commit `aa065ea`) escalated the two round-13 out-of-scope decisions as blockers: `from . import shared; shared.router...` and a keyword-preceded regex literal (`return /"/`) were confirmed still-live bypasses, reproduced against current code before touching anything, not just re-affirmations of the earlier documented scope call. Fixed both: `_module_import_aliases` now also resolves `from . import name`/`from .. import name` as a module identity when a submodule file actually named `name` exists (checked via `module_paths`), leaving `from . import name` where `name` is a plain name bound in `__init__.py` to the pre-existing name-edge mechanism, which already covers that sub-case correctly — so the statement's two genuinely ambiguous resolutions are each handled by the mechanism that actually matches them; bare `import X.Y.Z` (no `as`) remains the one still out-of-scope case. Added `_JS_REGEX_KEYWORDS` and `_last_word` (word-level, not char-level, lookback) so a keyword-preceded regex is now correctly distinguished from a real identifier ending the same way (verified an identifier literally named `returned` still divides correctly, confirming word-boundary matching). Corrected the round-13 decision log's two "documented, not used in this repo today" entries rather than leaving them standing as if still accurate — see the superseding entries. Verified: `from . import shared` and `from .. import shared` (two levels) both resolve correctly; the `__init__.py`-bound-name sub-case and a control case stay unaffected; `return`/`typeof`/`instanceof`/`case`-preceded regexes are all caught; all prior regression cases (router and JS/TS) replayed with nothing flipped. `pytest tests/architecture` (24 passed), both changed files against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Fifteenth GitHub PR #96 review round (repeat review of commit `5d4c6ac9`, GitHub review #5068785118, CI fully green on all three required jobs) found each round-14 fix was itself a narrower generalization than the underlying logic actually supported: `_module_import_aliases`'s submodule-file check only fired for bare relative `from . import name`, missing the identical-logic absolute case `from anytoolai_platform_api.routers import demo`; and the regex heuristic's `)`-is-always-a-value rule missed a control-flow condition's closing paren (`if (ok) /"/...`), a statement boundary rather than a value. Both root-caused as the same mistake one level up from round 13's own diagnosis: fixing the *literal shape* of a reported example instead of the general rule the example was an instance of. Fixed both by generalizing rather than special-casing further: dropped the `node.module is None and node.level > 0` restriction entirely, so every `ast.ImportFrom` (relative or absolute) gets the same submodule-file check — explicitly verified this doesn't regress the repo's own dominant import pattern (`from pkg.routers.demo import router as demo_router`, where `router` isn't a submodule); added `paren_stack`/`_JS_CONTROL_KEYWORDS_BEFORE_PAREN` so a condition paren's close clears `last_sig` instead of marking it a value, while an ordinary function-call paren's close still does. Verified: absolute and qualified-relative submodule imports resolve; the real `main.py` pattern is unaffected; `if`/`while`/`switch`-condition-preceded regexes are all caught; a real function call's division (including one nested inside a condition body) is unaffected; nested parens resolve the stack correctly; the full prior regression table (router identity + JS/TS, all rounds) replayed with nothing flipped. `pytest tests/architecture` (24 passed), both changed files against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Sixteenth GitHub PR #96 review round (repeat review of commit `bf66d329`) confirmed the router-identity blocker fixed and found one remaining JS/TS scanner gap: the round-15 control-paren heuristic loses a preceding keyword whenever a line break or comment separates it from `(`, because `_last_word` read from `current` (line-scoped, resets every `\n`) while `last_sig` persists across lines — the same "two independently-updated copies of one state machine drift apart" class this file's decision log has already named three times. Reproduced first (`if\n(ok) /"/...` truncates the real hardcode; a comment-separated variant reproduces identically). Fixed at the root rather than patching the paren case alone: replaced the lazy `_last_word(current)` read with a persistent `word_buf`/`last_word` pair maintained by one shared `_note(char)` closure, called from every character-consuming branch (string-open, `(`, `)`, generic fall-through) instead of each managing `last_sig` independently. While rewriting, caught and fixed a second bug in the identical class via self-review before it was externally reported: the newline branch never called `_note` at all, so the *existing* round-14 keyword-regex check (`return\n/re/`, no paren involved) had the same loss-across-a-line-break bug — added a `_note("\n")` call there too, since a newline is itself a word-boundary character. Verified: the exact `if\n(...)` and comment-separated cases now find the hardcode; the analogous `return\n/re/` case is also fixed; every same-line paren/keyword regression case from rounds 14–15 stays unaffected; the full prior regression table (router identity + all JS/TS cases across every round) replayed with nothing flipped. `pytest tests/architecture` (24 passed), both changed files against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-08-31 | Seventeenth GitHub PR #96 review round (repeat review of commit `9a4d935`) found the round-16 fix held for newlines/line-comments, but block-comment entry didn't call the finalization helper either, so a keyword immediately followed by `/*...*/` and then a regex (`return/*note*//"/`) still lost the keyword. The user explicitly rejected patching this one more branch ("НОРМАЛЬНО ПОПРАВЬ! А НЕ КОСТЫЛЬ!") — the third review round in a row to find a different branch that forgot to call the shared `_note`/finalize helper, evidence the per-branch-opt-in mechanism itself was the weakness, not any one branch. Restructured `_strip_comments` instead of patching further: identifier characters are now handled by exactly one dedicated branch (the only place `word_buf` grows), and every other character passes through one unconditional `_finalize_word()` call before any branch-specific logic runs — no branch can forget to finalize anymore, because it isn't part of any branch's own responsibility. This closes the reported block-comment case, the not-yet-reported line-comment case, and the zero-separator case (`return/"/...`, no space or comment at all) in one change. Caught and fixed a self-introduced regression while restructuring, before calling it done: an intermediate version moved the `\n`-handling branch after the `in_block_comment`/`in_string` checks, which broke multi-line string/comment line-splitting (a newline consumed while inside an active string/comment stopped flushing `lines`, collapsing physical lines and shifting later line numbers) — caught by re-running the existing multi-line template-literal case, fixed by keeping `\n` as the unconditional first check exactly as before. Verified: the exact review case, a block-comment-separated keyword-and-paren, a *multi-line* block comment between a keyword and a regex, and a real identifier followed by a block comment then real division (confirmed to stay division) all resolve correctly; the multi-line line-splitting case re-verified line-by-line; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `pytest tests/architecture` (24 passed), the changed file against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Eighteenth GitHub PR #96 review round (repeat review of commit `8606fcc`) found the round-17 structural fix held, but both keyword checks (`_JS_REGEX_KEYWORDS`, `_JS_CONTROL_KEYWORDS_BEFORE_PAREN`) match `last_word` against their keyword sets on spelling alone, so a *property* named like a keyword (`config.default`, `obj.if`) is indistinguishable from the real keyword — reserved words are valid JS/TS property names. `config.default / "openai/gpt-4.1".length` misclassified the following `/` as a regex start, and `_regex_literal_end` then used the `/` inside the nearby model literal as a fake terminator, stripping the `openai/` provider prefix off the hardcode entirely. Reproduced first, then checked the sibling paren-keyword check for the identical shape before fixing anything (given round 16's precedent of both checks sharing bugs) and found `obj.if(x)` broken the same way, not yet reported — fixed both together. Added `last_word_is_property`, set from `word_starts_after_dot` (was the character immediately before the word's first character a `.`?, captured at the moment a new word starts accumulating, before `last_sig` itself moves on) and carried into `last_word_is_property` on finalization; both keyword checks now additionally require `not last_word_is_property`. Verified: the exact review case and the analogous paren case both leave the real hardcode/regex content intact (confirmed by inspecting the stripped output directly, not just the offender result); a genuine `default` keyword (a `switch` statement) and a genuine control keyword before a paren are both still correctly recognized; optional-chaining property access (`config?.return`) is also correctly excluded; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `pytest tests/architecture` (24 passed), the changed file against the real repository tree, `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Nineteenth GitHub PR #96 review round (repeat review of commit `2cfeec8`) found the round-18 property-name fix held, but one gap remained specific to `.jsx`/`.tsx`: `<` isn't in `_REGEX_PRECEDED_BY_VALUE` (correctly, for `.js`/`.ts`, where `a < /re/` is a real idiom), so a JSX/TSX closing tag's `</` was misclassified as a regex start, and `_regex_literal_end` could then use a later real model literal's own `/` as a fake terminator, stripping the `openai/` prefix off it. Reproduced first, then checked repo exposure before shaping the fix: 36 real `.jsx`/`.tsx` files with real closing tags exist under `SCAN_ROOTS`, and no scanned file (JSX or not) contains a `<` immediately followed by a real regex literal. Fixed by adding a `jsx: bool = False` parameter to `_strip_comments` (`_regex_offender` passes `path.suffix in (".jsx", ".tsx")`) that excludes `<` from qualifying as "not a value" only when true, so `</` never starts a regex in JSX-capable files while the existing `a < /re/`-is-a-regex behavior for plain `.js`/`.ts` (where no closing tag can ever appear) stays exactly as it was — deliberately not broadened past what the file-type-dependent ambiguity actually justifies. Verified: the exact review case and a JSX fragment closing tag (`</>`) both now find the full hardcode; a real regex literal elsewhere in the same JSX file is still correctly recognized; a real `a < /re/` comparison in a non-JSX file is confirmed unaffected; `pytest tests/architecture` (24 passed) exercises all 36 real `.jsx`/`.tsx` files with no new false positives; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Twentieth GitHub PR #96 review round (repeat review of commit `c81265c`) confirmed the round-19 closing-tag fix works, and found one distinct, qualitatively different gap: the scanner still applies `//` JS-comment rules while scanning raw JSX element *text* (`<div>https://example.com</div>`), which isn't JavaScript and has no comment syntax at all — a same-line real hardcode after a JSX-text URL was silently truncated. Unlike every prior JS/TS scanner finding in this file (all local character/word heuristics), correctly fixing this needs real nested JSX-text/expression tracking — a second hand-rolled parser, the exact ceiling this file's decision log already accepted for the JS/TS path. Rather than build that tracker, disabled `//` line-comment recognition entirely for JSX-capable files (block comments and regex-literal detection unaffected) — the conservative direction for a boundary guard, since it can only ever make the scanner check more content (occasional false positive on a real inline comment), never silently miss a real hardcode. `.js`/`.ts` (which can never contain JSX) are completely unaffected. Verified: the exact review case now finds the hardcode; block comments and the round-19 regex fix both still work in JSX files; a genuine `//` comment in a JSX file is confirmed to scan its content instead of truncating; `.ts` `//` truncation is confirmed unaffected; `pytest tests/architecture` (24 passed) exercises all real `.jsx`/`.tsx` files with no new false positives from any real inline comment; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Twenty-first GitHub PR #96 review round (repeat review of commit `ddc1c136`) found round 20's own fix was itself flawed, not just incomplete: excluding `"//"` from the markers considered let a `//` comment's own text fall through to the ordinary character-by-character lexer, so a comment containing `/*` (`const el = <div />; // /* note`) opened a real, never-closed `in_block_comment` state that silently swallowed the entire rest of the file — worse than the original truncation bug. Root cause: "not a truncation point" was implemented as "feed it to the same stateful lexer that parses real code", which is a different and wrong claim — comment prose can coincidentally look like lexer-mutating syntax. Reproduced first, exactly as reported. Fixed with a genuine `in_line_comment` state (reset every `\n`): every character while in this state is appended to `current` verbatim through exactly one branch, with no other lexer logic running over it at all, so the comment's content stays available for the model-string regex (round 20's actual goal) without being able to mutate state for anything after it. `.js`/`.ts` completely unaffected (the new branch only fires when `jsx` is true). Verified: the exact review reproduction now finds the hardcode on the next line instead of losing the rest of the file; the round-20 raw-JSX-URL case is still fixed; a genuine `//` comment's content is still scanned; additional stress cases (an unterminated quote inside a comment, two separate comments across two lines) confirmed not to corrupt state; block comments, the round-19 closing-tag fix, and real regex literals all still work in JSX files; `pytest tests/architecture` (24 passed) exercises every real `.jsx`/`.tsx` file's actual comments with no new false positives or silent losses; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Twenty-second GitHub PR #96 review round (repeat review of commit `669f7446`) confirmed the round-21 `// /*` state-leak fix works, and found the symmetric gap: raw JSX text can contain `/*` literally (`<pre>Use /* to start a comment</pre>`), no comment semantics there, but the scanner still unconditionally opened `in_block_comment` with no guaranteed closing `*/`, swallowing the rest of the file — the same failure shape as round 21's finding, via `/*` instead of `//`. Reproduced first. Fixed by applying the round-21 lesson from the start: `/*` in JSX-capable files is now treated as two ordinary, non-comment characters (never opens `in_block_comment`), with `last_sig` deliberately biased so a following `/` reads as division/text rather than a fake regex start. Caught a second, self-introduced bug from this same fix via the established regression suite before calling it done, not from a fresh review round: a genuine block comment's own closing `*/` now also passed through as ordinary characters, and its `/` was itself misread as opening a *new* fake regex, consuming forward through a real hardcode on the same line — fixed by excluding a `/` immediately preceded by `*` from the regex decision when `jsx` is true, mirroring the existing `<` exclusion from round 19. Verified: the exact review case and a raw-JSX-text `/*` followed by an unrelated later `/` both now leave the hardcode intact; a genuine block comment's content is scanned correctly and no longer corrupted by its own `*/`; the round-19/20/21 fixes and real regex-literal recognition all still work in JSX files; `.ts`/`.js` block comments confirmed completely unaffected; `pytest tests/architecture` (24 passed) exercises every real `.jsx`/`.tsx` file's actual block comments with no new false positives or silent losses; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Twenty-third GitHub PR #96 review round (repeat review of commit `9ab4c764`) confirmed the round-22 raw-JSX-`/*` fix works, and named the underlying *pattern* rather than one more instance: a plain `/` starting ordinary raw JSX text (`<div>/docs {"openai/gpt-4.1"}</div>`) still gets skipped via `_regex_literal_end`, whose "closing" delimiter can be a real hardcode's own separator — enumerating specific shapes (`</`, `//`, `/*`, `*/`) can never be complete, since any `/`-then-later-`/` pair in raw JSX text can be misdetected regardless of context. The review explicitly offered a conservative alternative: never remove a source range based on a regex-literal heuristic when JSX context is unknown. Reproduced first. Implemented that alternative literally: for `jsx == True`, a span the heuristic decides looks like a regex is still *recognized* (so a quote inside it still can't corrupt `in_string` state, preserving the original reason regex-skipping exists) but its characters are now kept in `current` instead of discarded — so even a wrong detection can no longer lose content. `.js`/`.ts` keep discarding real regex-literal content exactly as before, since that behavior is unaffected by any reported problem and 20+ rounds of regression coverage already depend on it. Verified: the exact review case now finds the full hardcode; a genuine regex literal in a non-JSX file is unaffected; a real regex literal in a JSX file no longer discards its surrounding content but doesn't false-positive on itself; the original quote-inside-a-regex protection stays intact with no corruption; every fix from rounds 18–22 stays unaffected; `pytest tests/architecture` (24 passed) exercises every real regex literal in every real JS/TS/JSX/TSX file with no new false positives; the full prior regression table (router identity + every JS/TS case across every round) replayed with nothing flipped. `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) stay green. | Commit. |
| 2026-09-01 | Twenty-fourth review round — the first from a new "team lead" reviewer persona ("Code-review (team lead #1)", reviewing commit `52d31cf`) — raised six findings. Verified each against current code before touching anything. Three were real, blocking gaps in this PR's own two new scanners: (1) `ROUTE_REGISTRATION_METHODS` omitted Starlette's `add_route`/`mount`, both inherited by `FastAPI`/`APIRouter` and confirmed present on the pinned `fastapi==0.137.0` — `app.add_route("/proposal_ai/status", endpoint)`/`app.mount("/proposal_ai", child_app)` registered undetected; (2) `test_litellm_model_strings_stay_in_provider_config.py`'s Python AST path only inspected `ast.Constant`/`ast.JoinedStr`, never `ast.BinOp`, so `MODEL = "openai/" + "gpt-4.1"` bypassed it entirely (each fragment alone doesn't match the provider/model regex), and the JS/TS line scanner had the identical bypass; (3) (non-blocking coverage gap) `SCAN_ROOTS` omitted `scripts/` even though nothing there currently hardcodes a LiteLLM string. Fixed all three with minimal, targeted changes: added `add_route`/`mount` to `ROUTE_REGISTRATION_METHODS` (no other logic needed — both already fit `_path_argument`'s existing first-positional/`path=` extraction); added `scripts/` to `SCAN_ROOTS`; added `_fold_string_concat` (a small recursive `ast.BinOp(Add)` folder, mirroring `_python_offender`'s existing "skip anything with real interpolation" intent — `"openai/" + name` stays unmatched) to the Python path, and `_concatenated_string_values` (joins adjacent quoted-string spans on one line connected only by whitespace + a single `+`) to the JS/TS path, explicitly scoped with a `ponytail:` comment to same-line, string-literal-operand-only concatenation rather than attempting general JS/TS expression folding — consistent with this file's existing, already-accepted JS/TS-path ceiling ("no dependency-free JS/TS tokenizer available"). The other three findings target files/scope this PR never touched and were explicitly *not* fixed here, logged as follow-up debt below: `test_no_direct_provider_calls_outside_gateway.py` (pre-existing, Python-import-only — no JS/TS provider-package-specifier or raw-HTTP-host enforcement exists at all today, not just for `@anthropic-ai/sdk`) and `test_no_prompts_inside_extensions.py` (pre-existing, literal-token-only — a structural `{role: "system", content: ...}` message shape passes unchanged) are both real gaps but in test files this PR's diff never modifies, a materially larger and separate boundary-hardening effort from ANY-25's own two-new-scanners/two-docs scope; the request for permanent parameterized temp-tree regression fixtures for both new scanners is a legitimate, non-blocking, large addition on top of an already very large diff (662 + 450 lines before this round). Verified: the exact `add_route`/`mount` case now caught (confirmed via a synthetic two-call FastAPI app: before the fix, `[]`; after, both paths found); the exact Python and JS/TS concatenation cases now caught, with negative controls (real interpolation `"openai/" + name`, an unrelated concatenation `"https://x.com/" + "docs"`) confirmed to stay unmatched; `scripts/` scanned with zero pre-existing offenders. `pytest tests/architecture` (24 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (981 passed) all stay green. | Commit. |
| 2026-09-01 | Twenty-fifth review round ("Code-review (me #17)", reviewing commit `c6ad212d`) raised two blocking findings against round 24's own work. (1) Escalated the two boundaries round 24 had scoped out as follow-up debt (JS/TS provider-package/raw-HTTP-host enforcement; structural system-role message-shape detection) as required by the ticket's own AC regardless of which file implements them — correct, and reversed (see decision log). Implemented both for real: `test_no_direct_provider_calls_outside_gateway.py` gained `test_no_direct_provider_js_sdk_imports` (a `from`/`require(...)` specifier scan against `PROVIDER_JS_PACKAGES` — `openai`, `@anthropic-ai/sdk`, `@google/genai`, `@google/generative-ai`, `cohere-ai`, `mistralai`, `@mistralai/mistralai` — no allowed-root exemption at all, since frontend must never import a provider SDK under any circumstance) and `test_no_direct_provider_api_host_references` (a substring scan for known provider API hosts — `api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`, `api.cohere.ai`, `api.mistral.ai` — across `.py`/`.ts`/`.tsx`/`.js`/`.jsx`, exempting the existing Python adapter/gateway roots the same way the pre-existing import checks already do); `test_no_prompts_inside_extensions.py` gained `_SYSTEM_ROLE_MESSAGE_RE` (`role["']?\s*:\s*["'`]system["'`]`, catching `{ role: "system", ... }` in TS and `"role": "system"` in JSON) and, since this file previously had zero vendor/build-dir exclusion at all despite a real `node_modules` existing under `extensions/kernel-demo-ce/` today, imported the canonical `SKIP_PATH_PARTS` (the same dedup already used elsewhere in this file set) rather than let the new regex scan arbitrary vendored code. (2) Confirmed the round-24 JS/TS concatenation fix was still line-scoped: `"openai/" +\n  "gpt-4.1"` (multi-line) and `"openai/" + ("gpt-4.1")` (grouping parens) both still bypassed it. Generalized rather than patching two more special cases (this file's own decision log already names that exact repeat-pattern risk): `_concatenated_string_values` now operates on the whole comment-stripped file text (built once via `"\n".join(lines)`) instead of one physical line at a time, with `_CONCAT_JOIN_RE` widened from `^\s*\+\s*$` to `^[\s()]*\+[\s()]*$` (`\s` already matches `\n`, so cross-line join is free; the widened character class tolerates grouping parens) — still bounded to string-literal operands only (`"openai/" + model` stays unmatched), documented as the JS/TS path's existing ceiling. `_regex_offender` now does a fast per-line pass first (unchanged, common case), then a second whole-text pass for a cross-line concatenation the per-line pass structurally can't see, using a new `_line_number_at` (bisect over precomputed line-start offsets) to report a real line number for a match found in the joined text. | Verified: the exact multi-line and grouping-paren cases from the review, plus the original round-24 single-line case, all now caught; negative controls (`"openai/" + name`, an unrelated multi-line `"https://x.com/" + "docs"` concatenation) stay unmatched; the exact JS-SDK-import, raw-fetch-host, and system-role-message examples from the review are all now caught via direct calls to each new detector; a full real-repo scan of `extensions/`, `apps/`, `packages/` finds zero pre-existing offenders for any of the four new checks (confirmed before writing them, not just after). `pytest tests/architecture` (26 passed — 2 new tests), `validate_architecture.py`, `validate-docs`, and `quick-check` (983 passed) all stay green. | Commit. |
| 2026-09-01 | Twenty-sixth review round ("Code-review (me #18)", reviewing commit `6a998fb0`) confirmed the round-25 boundary work substantially closed the gaps, and found two more, both real: (1) the round-25 Python provider-SDK checks only covered `openai`/`litellm` (pre-existing) — `anthropic`, `google.genai`, `cohere`, `mistralai` (all named in `docs/architecture/llm-runtime.md`'s own forbidden list) had no Python import check at all, so `import anthropic; client = anthropic.Anthropic()` anywhere outside the adapter boundary passed clean; (2) the round-25 JS/TS import-specifier regex (`(?:from|require\()\s*["']...`) only recognized `from "pkg"`/`require("pkg")`, missing a bare side-effect `import "pkg"` and a dynamic `import("pkg")`/`await import("pkg")` — all three real, distinct ways to import a module in JS/TS. Reproduced both against current code before touching anything. Fixed both: added `_assert_no_direct_module_imports_outside_adapter` (a small shared helper reusing the already-existing `_imports_module`) plus four new explicitly-named test functions (`test_no_direct_anthropic_imports_outside_provider_adapter`, `..._google_genai_...`, `..._cohere_...`, `..._mistralai_...`), mirroring the existing `openai`/`litellm` tests' structure rather than parametrizing (no precedent for `pytest.mark.parametrize` anywhere in `tests/architecture/`, and per-provider named tests read better in CI output) — left the two pre-existing `openai`/`litellm` test functions themselves untouched to keep the diff minimal; widened `_JS_IMPORT_SPECIFIER_RE` from `(?:from|require\()` to `(?:from|require\(|import\(?)` — `import\(?` covers both the bare side-effect form (no paren) and the dynamic form (`import(`) with one alternative, verified this doesn't spuriously match `import { X } from "pkg"` (the bare "import" there isn't immediately followed by a quote) or a string literal that merely contains the word "import". Verified: all three exact review examples (`import "openai";`, `(await import("openai")).default`, `await import("@anthropic-ai/sdk")`) now caught by the regex; the four new Python provider checks confirmed to have zero pre-existing offenders in the real repo tree before being added; existing `from`/`require(` cases and 2 negative controls (a relative-path `from "./local"`, a string literal containing the word "import") replayed with nothing flipped. `pytest tests/architecture` (30 passed — 4 new tests), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Twenty-seventh review round ("Code-review (me #19)", reviewing commit `0bb69db8`) confirmed the round-26 provider-SDK/import-form coverage was substantially improved, and found two more direct bypasses in that same round's own new checks. (1) `_assert_no_direct_module_imports_outside_adapter("google.genai")` relies on `_imports_module`, which only compares `ast.ImportFrom.module` itself against the target string — but the canonical Google GenAI SDK import is `from google import genai` (`module="google"`, imported name `"genai"`), which never literally contains `"google.genai"` anywhere in its own AST, so it passed the check clean. The exact same parent-module-plus-child-name shape `_imports_provider_adapter` already handles correctly for its own "adapters" case, just not generalized into the shared `_imports_module` helper every other provider check relies on. (2) The round-26 `_JS_IMPORT_SPECIFIER_RE` widening only added `["']` as delimiters; a no-interpolation template-literal specifier (`` import(`openai`) ``, valid, common JS/TS) still wasn't recognized. Reproduced both against current code before touching anything. Fixed both: `_imports_module` now also splits a dotted `module_name` into `(parent, child)` and additionally matches `from <parent> import <child>` — verified this doesn't affect the existing non-dotted `openai`/`litellm`/`pydantic_ai` checks (empty `parent` short-circuits the new branch) and correctly stays `False` for an unrelated `from google import protobuf`; widened `_JS_IMPORT_SPECIFIER_RE`'s quote class from `["']` to `` ["'`] `` (backtick alongside the existing two), verified a genuinely interpolated specifier (`` import(`${pkg}`) ``) captures `${pkg}` literally rather than evaluating it, which never equals any entry in `PROVIDER_JS_PACKAGES` and so still can't false-positive. Verified: the exact `from google import genai` case and both exact review's backtick-specifier cases now caught; existing `from`/`require(`/bare-`import`/`import(` cases (quoted forms) replayed with nothing flipped; a real-repo scan of all four new Python provider checks plus the JS/TS import check confirms zero pre-existing offenders. `pytest tests/architecture` (30 passed — no new test count change, existing checks widened in place), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Twenty-eighth review round ("Code-review (me #20)", reviewing commit `367ae0b3`) confirmed both round-27 fixes hold, and found one more direct bypass in the same JS/TS import guard: `_JS_IMPORT_SPECIFIER_RE`'s `require\(`/`import\(?` alternatives require the `(` immediately adjacent to the keyword, but `require ("openai")`/`await import ("@anthropic-ai/sdk")` (ordinary whitespace before the paren, valid JS/TS) matched neither `require\(` — no space allowed — nor `import\(?` — the optional `(` can't skip over an intervening space either — so both stayed invisible. Reproduced both exact cases against current code first. Fixed by inserting `\s*` between the keyword and its `(`: `require\(` → `require\s*\(`, `import\(?` → `import\s*\(?` (the `?` still makes the whole `\s*\(` group optional together, preserving the bare side-effect `import "pkg"` case with no parens at all). Verified: both exact review cases now caught; every prior case (`from`, `require(`, bare `import`, `import(`, quoted and backtick specifiers) replayed with nothing flipped; the 2 existing negative controls (`from "./local"`, a string literal containing the word "import") stay unmatched. `pytest tests/architecture` (30 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Twenty-ninth review round ("Code-review (me #21)", reviewing commit `483fceb8`) confirmed the round-28 whitespace-before-paren fix holds, and found the JS/TS provider-SDK guard's specifier check used exact set membership (`match.group(1) in PROVIDER_JS_PACKAGES`), so a subpath import from a forbidden package — `import Completions from "openai/resources/chat/completions"`, `import Messages from "@anthropic-ai/sdk/resources/messages"` — still loads the SDK directly but never equals a bare package name, staying invisible. Reproduced both against current code first. Fixed with a small `_is_forbidden_js_specifier` helper: a specifier is forbidden when it equals a package in `PROVIDER_JS_PACKAGES` *or* starts with `f"{package}/"` — the `/` boundary is what keeps an unrelated package sharing a prefix (`openai-compatible`) from false-positiving against `openai`, exactly the risk the review itself called out. Verified: both exact subpath cases (unscoped `openai/...` and scoped `@anthropic-ai/sdk/...`) now caught; `openai-compatible` stays unmatched; the bare-package case and a control unrelated specifier (`./local`) both still resolve correctly. `pytest tests/architecture` (30 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Thirtieth review round — second from the "team lead" persona ("Code-review (team lead #2)") — raised five blocking findings, all verified real against current code before touching anything: (1) `test_no_product_specific_endpoints.py`'s `_string_value`/`_module_string_constants` resolved a direct literal or a name-to-literal reference but not `ast.BinOp(Add)` concatenation, so `@router.get("/proposal_" + "ai/status")` and `PATH = "/proposal_" + "ai/status"; @router.get(PATH)` both registered undetected — the same class of gap round 24 already fixed for the LiteLLM scanner, just not this file; (2) the same file's route discovery only recognized method calls on a tracked router/app (`router.get(...)`) or the `prefix=` keyword, never standalone Starlette route-object construction (`FastAPI(routes=[Route("/proposal_ai/status", endpoint)])`, `WebSocketRoute`, `Mount`) — a real, distinct route-registration shape with no router/app receiver to check at all; (3) `test_no_prompts_inside_extensions.py` only scanned `.ts`/`.tsx`/`.md`/`.json`, so a plain `.js` background script/service worker (a real, common Chrome Extension file shape) was invisible to the round-25 structural system-role check; (4)/(5) `test_no_direct_provider_calls_outside_gateway.py`'s `_JS_EXTS` and `test_litellm_model_strings_stay_in_provider_config.py`'s `SCAN_EXTS` both omitted `.mjs`/`.cjs`, even though `scripts/agent/validate_architecture.py`'s own canonical `JS_TS_EXTS` already includes both — three independently hand-rolled JS-extension sets had already drifted from each other and from the general validator. Fixed all five. (1)+(2): generalized `_string_value` to also fold `ast.BinOp(Add)` recursively (mirrors `_fold_string_concat` from the LiteLLM scanner), and rewrote `_module_string_constants` to build its dict via `_string_value` itself instead of a separate `ast.Constant`-only check, so a later constant can reference an earlier one and a concatenated value folds the same way a direct path does; added `ROUTE_OBJECT_CONSTRUCTORS = {"Route", "WebSocketRoute", "Mount"}` with its own `_route_object_import_aliases` — deliberately a *separate* alias dict from `_route_target_import_aliases`/`ROUTE_TARGET_CONSTRUCTORS`, not merged into it, because `_is_route_target_call`/`_direct_router_names` treat any name in that dict as "this creates a router/app object" and merging would wrongly make `x = Route(...)` look like a router binding too (verified this stays `False` after the change) — and a new `elif func_name in ROUTE_OBJECT_CONSTRUCTORS` branch in `_route_path_literals_for_tree` with no `called_on_router` gate, since these are standalone constructions, never a method call on a router. (3)/(4)/(5): centralized the JS-extension set — renamed `test_no_direct_provider_calls_outside_gateway.py`'s `_JS_EXTS` to public `JS_TS_EXTS` (now including `.mjs`/`.cjs`, matching the general validator) and had both sibling files import it instead of hand-rolling their own copy (`test_litellm_model_strings_stay_in_provider_config.py` already imported `SKIP_PATH_PARTS` from this same neighbor — this follows the identical, already-established dedup pattern); added `.mjs`/`.cjs` entries to `_COMMENT_MARKERS_BY_SUFFIX` (`("//",)`, same as `.js`). Verified: the exact concatenated-path and concatenated-module-constant cases now caught; the exact `Route`/`WebSocketRoute`/`Mount` composition case now caught, with a negative control (`x = Route(...)` doesn't get treated as a router/app name) confirmed clean; a `background.js` with a structural system-role message now caught; `.mjs` now included in both the provider-SDK-import file set and the LiteLLM scanner's file set. `pytest tests/architecture` (30 passed — no new test count, existing checks widened), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Thirty-first review round ("Code-review (me #22)", explicitly labeled "repeat review of `648433c3`") restated the same three findings round 30 had just fixed — concatenated route paths/constants, `Route`/`WebSocketRoute`/`Mount` composition, and the three-way drifted JS-extension sets. `648433c3` is round 29's commit, not round 30's (current HEAD at review time) — this review ran against a commit one round stale, before the fixes it's describing already landed. Verified all three directly against current code with the same repro scripts used in round 30 rather than assuming staleness from the commit hash alone: the exact concatenated-path/constant case, the exact `Route`/`Mount` composition case, and the exact `background.js` structural-prompt/`.mjs` provider-import/`.mjs` model-string cases are all already caught. No code changes made — nothing to fix. The only substantive remainder in these findings ("add regressions for both direct and constant-backed forms", "add regressions for at least `Route` and `Mount`") restates the already-tracked, already-deferred non-blocking follow-up debt item (permanent parameterized temp-tree regression fixtures for the two new scanners), not a new ask. `pytest tests/architecture` (30 passed) reconfirmed green, no regression. | None — awaiting a review against the current commit. |
| 2026-09-01 | Thirty-second review round ("Code-review (me #23)", reviewing commit `d30fa400`) confirmed the round-30 fixes hold (concat, route-object composition, JS-extension centralization), and found `_string_value` still didn't fold `ast.JoinedStr` (an f-string), so `@router.get(f"/proposal_ai/status")` and `PATH = f"/proposal_ai/status"; @router.get(PATH)` — both fully static, no real interpolation — registered undetected, inconsistent with the LiteLLM scanner in the same PR already applying the identical "every part a literal `Constant`" rule to `JoinedStr`. Reproduced against current code first (confirmed empty `JoinedStr` from a no-interpolation f-string, not simplified to a plain `Constant` by the parser). Fixed by adding the same rule `_python_offender` already uses to `_string_value`: a `JoinedStr` folds to the joined string only when every part is a literal `ast.Constant` (no `ast.FormattedValue` at all); a genuinely interpolated f-string stays unresolved. Verified: both exact review cases (direct and constant-backed) now caught; a negative control (`f"/safe/{seg}"`, real interpolation) confirmed to stay dynamic, not folded into `constants` or matched as a literal. `pytest tests/architecture` (30 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Thirty-third review round ("Code-review (me #24)", reviewing commit `4e88201`) confirmed the round-32 no-interpolation-f-string fix holds, and found the same `_string_value` `JoinedStr` handling still required *every* part to be a literal `Constant`, so a `FormattedValue` interpolating a known module constant (`PRODUCT = "proposal_ai"; @router.get(f"/{PRODUCT}/status")`) still returned `None` even though the interpolated value is already resolvable — a normal way to compose route prefixes/segments from constants, not a genuinely dynamic expression. Reproduced against current code first. Fixed by rewriting the `JoinedStr` branch to accept a `FormattedValue` part too, resolving its `.value` recursively through `_string_value` itself (so a constant-referencing-a-constant chain folds the same way `_module_string_constants` already supports for plain assignments) — but only when `conversion == -1` (no `!r`/`!s`/`!a`) and `format_spec is None`, since either would change the interpolated text in a way plain string concatenation can't reproduce, and is treated as unresolvable rather than guessed at. Verified: the exact review case now caught; three negative controls — a genuinely dynamic segment (`f"/safe/{segment}"`), a `!r`-converted constant (`f"/{PRODUCT!r}/status"`), and a format-spec'd constant (`f"/{PRODUCT:>10}/status"`) — all confirmed to stay unresolved, not silently folded into something wrong. `pytest tests/architecture` (30 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (987 passed) all stay green. | Commit. |
| 2026-09-01 | Thirty-fourth review round ("Code-review (team lead #3)", reviewing commit `bc41886`) reported four blocking bypasses, all verified real against current code: (1) the LiteLLM gate's `JoinedStr` branch still required every part to be a literal, so `PROVIDER = "openai"; MODEL = f"{PROVIDER}/gpt-4.1"` passed, and the JS/TS line scanner had no notion of `` `${provider}/gpt-4.1` `` with `const provider = "openai"`; (2) the provider-host gate was a raw substring search, defeated by `"https://api." + "openai.com/v1/responses"`; (3) the extension-prompt gate matched only a literal `role: "system"`, so `role: SYSTEM_ROLE` with `const SYSTEM_ROLE = "system"` passed, and `instructions`/`systemInstruction`/`system` payloads had no check at all; (4) the endpoint gate resolved `ast.Name` only against same-file constants, so `paths.py: PROPOSAL_STATUS_PATH = "/proposal_ai/status"` + `from .paths import PROPOSAL_STATUS_PATH` (or `paths.PROPOSAL_STATUS_PATH`) passed. Fixed at the root rather than per finding: a new shared `static_string_resolution.py` owns static string resolution for every gate — Python `PythonModules` (parse, index every dotted name a file can be imported as, resolve module-level constants across `from X import NAME`/`import X as m`/`from pkg import mod` edges to a fixed point, fold `+`/f-strings with the round-33 conversion/format-spec guard) and JS/TS `JsModules` (the hand-rolled comment/regex-literal lexer moved here verbatim as `strip_js_comments`; `const`/`let`/`var` string bindings resolved across relative `import { NAME } from "./x"` edges to a fixed point; `js_string_expr_at` folds `+` chains, grouping parens, and `${NAME}` template holes of a known constant). Each gate now consumes resolved values: the LiteLLM gate scans `python_string_values`/`js_string_values`; the host gate checks raw text *and* folded values in both languages; the prompt gate resolves the value after any `role`/instruction key through `js_string_expr_at` (plus a real `json.loads` walk for `.json`); the endpoint gate's `_path_argument` resolves through `python_string_value` with cross-module constants and module aliases. `SKIP_PATH_PARTS`/`JS_TS_EXTS` moved to the shared module (gaining `.output`/`.wxt` — wxt build bundles under `extensions/` were being scanned). Every gate is a `check_*(root, ...)` function, and 10 isolated `tmp_path` regressions cover each review case plus negative controls (a dynamic f-string/template, a `!r`-style unresolvable, a typed `role: string` interface, `role: "user"`, a pass-through `instructions: response.instructions`). Verified against the real tree that nothing passes vacuously: the endpoint gate still finds 18 route literals across 8 router-bearing files, cross-module constants really resolve in the real package (`REQUEST_ID_HEADER` into `main.py`), the LiteLLM gate folds 5.6k Python/2.7k JS values. `pytest tests/architecture` (40 passed, in ~3s instead of 54s after `iter_source_files` switched from `rglob` to a pruned `os.walk`), `validate_architecture.py`, `validate-docs`, and `quick-check` (997 passed) all green. | Commit. |
| 2026-09-01 | Thirty-fifth review round ("Code-review (me #25)", reviewing commit `e37f216`) confirmed round 34's four fixes hold, and found three new blocking false-negatives, all in round 34's own new code: (1) `check_prompts_inside_extensions()` only matched `key: value` syntax, so an ES2015 shorthand property (`const role = "system"; const messages = [{ role, content }]`) built the exact same request object at runtime but matched neither `_SYSTEM_ROLE_MESSAGE_RE` (no `:`) nor `_JS_REQUEST_KEY_RE` (same reason); (2) `python_modules()`/`module_import_aliases()` walked the whole tree (`ast.walk`) for imports, so a function-local `from .safe_paths import PATH` could overwrite the real module-level `PATH` in the shared `constants[path]` map even though it can't and doesn't change what a module-level decorator actually sees at runtime — the same scope-pollution class already avoided for plain assignments (`tree.body`-only), not yet applied to imports; (3) `check_provider_api_host_references()` excluded allowed adapter/gateway roots from `python_paths` *before* building `PythonModules`, so a constant defined in an allowed module (`gateway/constants.py: API_PREFIX = "https://api."`) couldn't be resolved into a disallowed consumer that completed the host locally (`API_PREFIX + "openai.com/..."`) — the exclusion needed to apply to reporting, not to the resolver's input graph. All three reproduced against current code first (each returned no offenders on the exact reported case). Fixed at the root: added `_JS_SHORTHAND_KEY_RE` (matches a tracked key immediately preceded by `{`/`,` and followed by `,`/`}`, looked up directly in the file's resolved constants) as a second pass in the prompt gate; added `module_level_imports()` to `static_string_resolution.py` (returns only `tree.body` import statements) and switched both `module_import_aliases()` and `python_modules()`'s constant-propagation loop onto it; rewrote `check_provider_api_host_references()` to build `PythonModules` from every Python file first and apply the allowed-root exclusion only when deciding what to report. Verified each exact case now caught, plus that the allowed module itself still never appears in the host gate's own output. `pytest tests/architecture` (43 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (997 passed) all green. | Commit. |
| 2026-09-01 | Thirty-sixth review round ("Code-review (me #26)", reviewing commit `1e985bc`) confirmed round 35's three fixes hold, and found two new blocking gaps, both in the JS/TS resolver's design from round 34: (1) `js_modules()` put every `const`/`let`/`var` declaration in one flat per-file namespace with no scope tracking, so a nested-function `const role = "user"` textually overwrote a module-level `const role = "system"`, and the shorthand check resolved the module-level `{ role }` reference to the wrong (locally-shadowed) value; separately, `let`/`var` were treated as immutable once declared, so `let role = "user"; role = "system";` still resolved to the stale `"user"`, and a LiteLLM provider built the same way could fold to a wrong (or missed) hardcode; (2) for `.jsx`/`.tsx` files, `strip_js_comments` deliberately preserves `/* ... */` text verbatim (it can't distinguish raw JSX text from real JS expression syntax), so a genuine block comment inside real object-literal syntax (`role /* request role */: SYSTEM_ROLE`, or before a shorthand `role,`) defeated the request-key regexes' whitespace-only adjacency requirement. Both reproduced against current code first. Fixed by replacing the flat namespace with genuine lexical scope tracking: `_js_block_path_at` computes the stack of enclosing `{ ... }` block ids at any position (skipping string-literal content via the existing literal spans), `JsModules.declarations` records every declaration as `(block_path, value)` instead of one flat `name -> value`, and the new `resolve_js_identifier(modules, path, name, position)` picks the innermost declaration whose block path encloses the query position — real shadowing instead of "whichever declaration is textually last." A `let`/`var` declaration is recorded with `value = None` (unresolvable, not its stale initializer) whenever a bare `name = ...` reassignment exists anywhere within its own scope; `const` needs no such check (JS itself forbids reassigning one). Every call site that previously read the flat `constants` dict (`js_string_expr_at`'s identifier operand, `_template_value`'s `${NAME}` holes — resolved as of the *template literal's own* position, since a hole's own offset sits inside the literal's span and would otherwise mis-scope, `js_string_values`'s file-wide scan, and the prompt gate's shorthand lookup) now goes through `resolve_js_identifier`. For (2), added `_WS_OR_COMMENT` (zero or more whitespace/block-comment runs) into `_JS_REQUEST_KEY_RE` and `_JS_SHORTHAND_KEY_RE` in place of plain `\s*` — a no-op for non-JSX files, where `strip_js_comments` already removes such a comment outright. Verified all five exact review cases now behave correctly (shadowing no longer leaks either direction in the prompt gate or the LiteLLM gate; reassignment resolves to unresolved, not a stale value; both JSX comment placements now detected), plus that a genuinely non-shadowed, non-reassigned outer constant still resolves normally. Real-tree sanity check: the LiteLLM gate's JS resolver still folds 2719 string values across the real 144-file tree (was 2723 under the old flat model — the small drop is the intentional tightening, not a resolution regression) in well under a second. `pytest tests/architecture` (51 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1006 passed) all green. | Commit. |
| 2026-09-01 | Thirty-seventh review round ("Code-review (me #27)", reviewing commit `a8cd111`) confirmed round 36's shadowing and JSX-comment fixes hold, and found two new blocking gaps: (1) round 36's own reassignment fix was too conservative — invalidating a reassigned `let`/`var` entirely (resolving to `None`) meant a *deterministically* reassigned real value (`let role = "user"; role = "system"; const messages = [{ role }];` — `role` is statically `"system"` at the use site, no branching involved) became invisible to the gate too, trading a wrong-value bug for a missed-detection bug — the opposite failure mode, and just as unsafe for a boundary gate whose whole purpose is to catch real violations; the LiteLLM gate had the identical bypass for a reassigned provider built into a template literal; (2) function/arrow parameter defaults (`function buildMessage(role = "system") { return { role }; }`, same for an `instructions` default and a default `provider` folded into a template model string) were never modeled as bindings at all — `JsModules.declarations` only recorded imports and `const`/`let`/`var`, so the shorthand/template lookup for a parameter name always returned `None` regardless of how statically known its default value was. Both reproduced against current code first. Fixed by replacing single-value-per-binding tracking with a write timeline: `JsModules.declarations[path][name]` is now `list[(block_path, timeline)]`, where `timeline` is a `(position, value)` list — a declaration's or parameter's own initializer, followed by any later reachable reassignment, sorted by source position. `resolve_js_identifier` first picks the innermost enclosing binding (unchanged shadowing logic from round 36), then within its timeline takes the *latest write at or before the query position* — the value genuinely in effect there, not "was this binding ever reassigned." Added `_js_param_default_events` (new `_JS_FUNCTION_SIGNATURE_RE`/`_JS_ARROW_SIGNATURE_RE`/`_JS_PARAM_DEFAULT_RE`): a parameter default with a real `{ ... }` body immediately following its signature becomes a mutable (never `const`) timeline-bearing binding scoped to that body's own block path — a concise-body arrow (`(role = "x") => role`, no block to anchor to) or an ambient/overload signature with no body at all is skipped, a documented ceiling. Self-caught a regression while implementing: cross-file import resolution (`resolve_js_identifier(modules, source, exported, 0)`) broke under the new timeline model, since position 0 is *before* any write has textually occurred — fixed by resolving an export at the end of the source file's text instead (the value a module's top-level code has actually settled to by the time evaluation finishes), and updated the two round-36 regression tests whose `== []` expectations the review explicitly said were now the wrong assertion to make (a static reassignment must be *detected*, not treated as safely absent) to assert the correct positive detection instead. Verified all five review cases plus a negative control (a parameter with no default, and one whose default is a genuinely dynamic call, stay unresolved). Real-tree sanity check: the LiteLLM gate's JS resolver now folds 2726 string values across the real 144-file tree (up from 2719 — the increase is real values newly caught, deterministic reassignments and parameter defaults among them, not a regression), still under 1.1s. `pytest tests/architecture` (54 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1009 passed) all green. | Commit. |
| 2026-09-01 | Thirty-eighth review round ("Code-review (me #28)", reviewing commit `b523337`) confirmed round 37's reassignment-timeline and parameter-default fixes hold for the straight-line cases, and found one real correctness gap: every write in a timeline was still collapsed into one deterministic value keyed purely by textual position, with no distinction between a write that always executes (a plain sequential statement) and one that only conditionally executes (inside `if`/a loop/etc.) — `let role = "system"; if (useUserRole) { role = "user"; } const messages = [{ role }];` resolved only to `"user"` (the textually-last write), even though `"system"` remains a real, reachable runtime value whenever `useUserRole` is false; the LiteLLM gate had the identical bypass for a conditionally-reassigned provider. The review correctly noted this is the mirror image of round 36's original bug: discarding an earlier value in favor of a conditionally-written later one is exactly the "wrong-value" failure mode the boundary gates exist to prevent, just introduced from the opposite direction. Reproduced against current code first. Fixed by changing what a timeline entry carries and how it's combined: each write now carries the *set* of values it could produce (usually one, but a name resolved from a conditionally-written source can itself already be multi-valued) instead of a single value, and each entry also carries its own block path (not just the group's). `resolve_js_identifier` replays a binding's timeline up to the query position and, for each write, *replaces* the reachable set when the write sits at the binding's own block path (a deterministic, always-executed statement) but *adds* to it (union, discarding nothing) when the write sits at a strictly deeper block path (behind a conditional it might not reach) — closing the exact bug reported while still correctly resolving a genuinely sequential, unconditional reassignment to only its final value (round 37's case, unchanged). `js_string_expr_at`/`_template_value` were generalized from single-value folding to a capped Cartesian-product combine (`_combine`, documented cap at 256 combinations — a real hardcode fed by more than a couple of conditional branches in one expression is vanishingly unlikely, and ponytail-appropriate given no real parser is available) so a `+` chain or a template hole with multiple statically-known possible values still folds correctly; `js_string_values` now yields one row per reachable value at a given position instead of assuming exactly one. The two prompt-gate call sites (colon-form and shorthand) were updated to flag a use if *any* resolved value is forbidden, not only a single deterministic one, via a new `_offending_value` helper. Verified both exact review cases now caught, plus the mirror case (a conditional branch introduces a *safe* alternative but the unconditional value is still forbidden and must still be caught) as an explicit regression. Real-tree sanity check: the LiteLLM gate's JS resolver folds 2727 values across the real 144-file tree (consistent with round 37's 2726 — no explosion, no false positives), runtime unchanged (~1.1s), and both gates stay clean against the real repository. `pytest tests/architecture` (57 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1012 passed) all green. | Commit. |
| 2026-09-01 | Thirty-ninth review round ("Code-review (me #29)", reviewing commit `308faff`) confirmed round 38's possible-value-set fix works for braced control-flow blocks, and found one real bypass: the deterministic-vs-conditional distinction was decided solely by comparing `{ ... }` block paths, but JS/TS control flow doesn't require braces — `if (useUserRole) role = "user";` (no braces at all) gives the reassignment the *identical* block path as the declaration (since no `{` was ever opened), so it was wrongly treated as an unconditional, deterministic write, discarding `"system"` even though it remains reachable whenever the condition is false; the LiteLLM gate had the same bypass for `if (useFallback) provider = "";`, folding only `"/gpt-4.1"` instead of also considering `openai/gpt-4.1`. Reproduced against current code first. Fixed by extending `_js_block_path_at` to recognize JS/TS control-flow keywords (`if`/`for`/`while`'s own `(...)` guard clause, or a bare `else` — `else if` is left to the following `if`, since both would close at the identical point anyway) and, whenever the token immediately following the guard isn't `{`, push a "virtual" block (drawn from the same globally-unique id space as real `{}` blocks, so it deepens a block path exactly the same way) standing in for the single braceless statement that follows; the virtual block closes at that statement's own terminating `;`, correctly popping every virtual block still open at that point together (so a chained `if (a) if (b) x = 1;` closes both at once) and correctly ignoring a `;` inside an un-skipped `(...)` (a `for (init; cond; update)`'s own semicolons). A `do` loop's braceless body (terminated by a trailing `while (...)`, not a `;`) is left unmodeled — not raised by the review, and rare in practice; documented as a ceiling. Verified both exact review cases now caught, plus a battery of related shapes: a braceless `while`, a braceless `for`, a chained braceless `if`/`else if`, a braceless bare `else`, `if`/`for` guard clauses containing their own semicolons and parens, a property literally named `if` (`obj.if`) correctly *not* treated as the keyword, and the round-37/round-38 unconditional-sequential and braced-conditional cases confirmed unaffected. Real-tree sanity check: the LiteLLM gate's JS resolver still folds 2727 values across the real 144-file tree (unchanged from round 38 — no explosion, no new false positives), runtime up modestly (~1.1s to ~2.6s for that one check, ~5s to ~8s for the whole suite — still well within reason), both gates stay clean against the real repository. `pytest tests/architecture` (61 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1016 passed) all green. | Commit. |
| 2026-09-01 | Fortieth review round ("Code-review (me #30)", reviewing commit `ee355da`) confirmed round 39's braceless-control-flow fix works for `if`/`for`/`while`, and found one real gap: a concise (expression-bodied) arrow function's default parameter, `const chooseModel = (provider = "openai") => \`${provider}/gpt-4.1\`;`, was still not modeled as a binding at all — `_js_param_default_events` only anchored a parameter's scope when it could find a real `{ ... }` body, and explicitly skipped concise arrows. The review's own literal example turned out to already resolve correctly by accident (verified by reproducing it before any fix): the naive `text.find("{", ...)` body-brace search latched onto the `{` inside the template literal's own `${` interpolation, and — since both that coincidental position and the template literal's true position fall inside the exact same string-literal span, which `_js_block_path_at`'s span-skip logic collapses identically — the two queries happened to land on the same (wrong-reason, right-answer) block path. Constructing the same underlying bug without that coincidence (`(provider = "openai") => provider + "/gpt-4.1"`, plain concatenation, no brace anywhere) reproduced a genuine miss, confirming the finding was real even though its own example wasn't the cleanest demonstration. Fixed by extending `_js_block_path_at` to push a virtual scope immediately after `=>` whenever it isn't followed by `{` — the identical mechanism round 39 already added for braceless control flow — and rewriting `_js_param_default_events`'s arrow branch to anchor a parameter's scope by checking only the token immediately after `=>`, matching the resolver's own rule exactly instead of guessing via a forward brace search (which could itself latch onto an unrelated `{` — a template hole, a parenthesized object literal like `=> ({ role })` — and mis-scope the parameter, a distinct fragility beyond just missing concise bodies, fixed as part of the same change since it shared the same root cause). The `function`-declaration branch (which always requires a real body) keeps its forward, now literal-span-aware search, since a return-type annotation can put real distance between the parameter list and the body brace. Verified the review's own example, the isolated non-coincidental reproduction, nesting inside an enclosing real block, a parameter used before an unrelated later object-literal brace in the same expression (the exact shape the old guessing logic would have mis-scoped), and a role-parameter concise arrow for the prompt gate. Real-tree sanity check: the LiteLLM gate's JS resolver still folds 2727 values across the real 144-file tree (unchanged — no explosion, no new false positives), runtime essentially unchanged. `pytest tests/architecture` (63 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1018 passed) all green. | Commit. |
| 2026-09-01 | Forty-first review round ("Code-review (me #31)", reviewing commit `c11ac4c`) confirmed round 40's concise-arrow-parameter fix works for the covered case, and found one real scope bug in the new virtual-arrow mechanism itself: a concise arrow's virtual scope only closed at `;`/`}`, but a concise arrow body is an *expression*, and JS expressions end other ways too — a comma when the arrow is a list/argument element (`const values = [(provider = "internal") => provider, \`${provider}/gpt-4.1\`]`), the enclosing bracket's own closing `)`/`]` with no trailing comma at all, or ASI at a newline in semicolon-free style (`const normalize = (provider = "internal") => provider` followed by a blank line then a new statement) — none of which the old `;`/`}`-only rule recognized, so the parameter's virtual scope stayed open long past the arrow's real end and leaked into unrelated sibling code, letting an inner safe/dummy parameter shadow and hide an outer forbidden binding; the prompt gate had the identical bypass. All three of the review's examples reproduced against current code first. Fixed by adding a unified bracket-depth counter tracking `(`/`[` nesting (kept deliberately separate from the real `{}` block stack used for lexical declaration scoping, since object-literal commas and statement-block commas share identical `{`/`}` syntax and can't be told apart without a real parser — documented as a narrower, remaining ceiling), and giving every virtual scope — control-flow or arrow-body alike — three closing triggers instead of one: a `,` at exactly its own opening bracket depth (a sibling list/argument boundary), a `)`/`]` that drops bracket depth strictly below its own opening depth (its enclosing bracket just closed), and (generalizing the existing `;` rule) either a `;` or a newline at global bracket depth 0. Implementing the newline rule first introduced a self-caught regression: a raw "newline at bracket depth 0 closes trailing virtuals" check fired on the newline ending a guard/`=>` token's own line — e.g. `if (cond)\n  role = "x";`, where the guard's own `(cond)` closes at end of the first line — before the actual body statement on the next line had even been reached, breaking round 39/40's own already-passing tests. Fixed by giving each virtual entry a `body_starts_at` position (the already-computed offset of its first real body token) and gating the `;`/newline close on `body_starts_at <= current position`, so the transitional whitespace between a guard and a next-line body is never mistaken for the body's own end. Verified all three exact review cases, plus a battery of related shapes: a braceless `if` body on the next line (confirming the self-caught regression stays fixed), a multi-line `for` guard, a chained braceless `if`/`if`, a concise arrow as a call's sole argument (closing-paren-terminated, no comma), an arrow followed by a comma then a sibling call argument reading the outer binding, and round 37/38's sequential-reassignment and braced-conditional cases (confirmed unaffected). Real-tree sanity check: the LiteLLM gate's JS resolver still folds 2727 values across the real 144-file tree (unchanged — no explosion, no new false positives), runtime essentially unchanged (~3s for that one check, ~8s for the whole suite). `pytest tests/architecture` (66 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1021 passed) all green. | Commit. |
| 2026-09-01 | Forty-second review round ("Code-review (me #32)", reviewing commit `f4d708c`) confirmed round 41's ASI/comma/bracket-close fixes hold, and found the one gap that round 41's own docstring had already flagged as a known ceiling was in fact still exploitable: a concise arrow used as an object-property value (`const config = { normalize: (provider = "internal") => provider, model: \`${provider}/gpt-4.1\` }`) still leaked its parameter into a sibling property, because the bracket-depth counter deliberately excluded `{`/`}` (a real statement block and an object literal are spelled identically, and round 41 accepted that as a remaining gap rather than guessing). The review's own multi-line example again turned out to pass by accident before any fix — reproduced first and confirmed the arrow's virtual scope actually closed via the *newline*-ASI rule (the property value happens to end its own line), not via any comma-based mechanism at all; a single-line version of the same object literal, with no newline to coincidentally rescue it, reproduced a genuine miss, confirming the finding as real. The review suggested a real JS/TS parser might be safer than "another delimiter heuristic," but a bounded heuristic was judged sufficient here, consistent with how this file has resolved every other JS/TS ambiguity so far (round 20's JSX regex-vs-division disambiguation, round 36 onward's block-path tracking) rather than adding a parser dependency for a test-only scanner. Fixed by classifying each `{` via the last significant character immediately before it: preceded by `)` (a function/if/for/while/catch header's own closing paren) stays a plain block, exactly as before; every other `{` (after `(`, `[`, `,`, `:`, `=`, an operator, a keyword, or the start of a statement) now also counts toward bracket depth the same way `(`/`[` already do, so a comma inside it can close a still-open virtual scope the identical way one inside `(...)`/`[...]` does; its matching `}` decrements bracket depth back down. The remaining, narrower misclassification this can't resolve (a bare block statement, or a `try`/`catch`/`finally`/`do`/`else`/class body reached with no parenthesized header right before it) was reasoned through explicitly: it only risks losing precision for a comma *inside* that one block, never leaking a scope past where it should have closed, since real lexical declarations are entirely unaffected — the safe direction this file has consistently favored throughout — so it's accepted and documented as a ceiling rather than chased with more special-casing. Verified both exact review cases, the isolated non-coincidental single-line reproduction, and a stress battery: a `useEffect(() => {...}, [dep])`-shaped real block followed by a comma and array (a very common real-world pattern, confirmed unaffected), a function body containing an internal multi-declarator comma (`let a = 1, b = 2`, confirmed not miscounted), a nested object literal with its own arrow-leak case inside a function body, a class body (deliberately misclassified, confirmed the failure stays safely contained), and round 41's own array-comma case (confirmed unaffected). Real-tree sanity check: the LiteLLM gate's JS resolver still folds 2727 values across the real 144-file tree (unchanged — no explosion, no new false positives), runtime essentially unchanged (~3s for that one check, ~8.8s for the whole suite). `pytest tests/architecture` (68 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1023 passed) all green. | Commit. |
| 2026-09-01 | Forty-third round: not a new review, but the user directly challenged the pattern across rounds 36-42 — seven consecutive rounds patching the same hand-rolled JS/TS scope scanner, with the review text itself offering "use a real JS/TS parser" as an explicit alternative in rounds 39, 40, and 42, each time answered with one more bounded heuristic instead. Agreed this was the wrong call by round 42 and replaced the whole scanner. Added `scripts/agent/js_scope_resolver.mjs`: parses every JS/TS file with the real TypeScript compiler (`typescript`, already a repo devDependency — this is not a new dependency), builds a per-file scope tree from real AST parent pointers (`Block`/`SourceFile`/a concise arrow's own node as a synthetic scope), and resolves every string-producing expression — literals, templates (each hole at its own true position), `+` chains, and identifier references — through genuine lexical shadowing and write order, exactly mirroring the model rounds 36-42 built by hand (a write at the binding's own scope is deterministic and replaces the reachable set; a write reached only through a conditional AST slot — an `if` `then`/`else`, a loop body, anywhere under `try`/`catch`/`switch` — is conditional and unions into it), plus cross-file `import { NAME } from "./x"` resolution against each source file's own exports. `static_string_resolution.py`'s entire JS/TS section (`strip_js_comments`, `_js_block_path_at`, the timeline/virtual-scope/bracket-depth machinery — roughly 880 lines accumulated over rounds 34-42) was deleted and replaced by ~130 lines that shell out to the script once per test run (batched over every file) and index its JSON result; `js_string_expr_at`/`resolve_js_identifier`/`js_string_values` became thin lookups into that index. The three gate files needed only mechanical updates (`js_string_expr_at`'s return type simplified from a `(value, end)` tuple to a plain value set since nothing used `end`; the prompt gate's `_WS_OR_COMMENT` comment-tolerance hack reverted to plain `\s*`, since the script already blanks every comment to same-length whitespace before any gate sees the text). Verified by re-running the full existing regression suite (every fixture from every round 34-42 finding, unchanged) with zero test-content edits needed — all 68 passed against the new implementation on the first attempt after fixing two bugs caught during manual verification before ever running pytest (a `+`-chain fold not threading a synthetic import "write" through the right code path; a naive ancestor walk in the determinism check that skipped past the immediately-enclosing statement, which would have wrongly classified every braceless `if` as deterministic again). Additionally confirmed, deliberately, that the rewrite closes two things never fixed at all — a `do` loop's braceless body (an explicitly accepted ceiling since round 39) and round 42's own just-documented remaining ceiling (an object-literal comma nested inside a `try`/class/bare-block body) — both resolve correctly with no special-casing, since a real parser has no notion of "which brace shape is ambiguous" in the first place. Real-tree sanity check: the resolver now finds 2967 root string values across the real 145-file JS/TS tree (up from 2727 under the old heuristic model — the increase is real coverage gained, not a regression, confirmed by all three gates staying clean against the real repository), and runs in ~0.4s for the whole batch (faster than the heuristic scanner's own ~3s, since a compiled parser beats a 50-pass Python fixed-point loop). `pytest tests/architecture` (68 passed, ~9.5s total including per-test Node subprocess startup), `validate_architecture.py`, `validate-docs`, and `quick-check` (1023 passed) all green. | Commit. |
| 2026-09-01 | Forty-fourth review round ("Code-review (me #33)", reviewing commit `231e0c2`) confirmed round 43's AST-based rewrite is the right direction and closes the object-property/concise-arrow leak, and found one real gap in the new `isDeterministicWrite` itself: it correctly rejected a conditional AST slot and a nested `Block` boundary, but never checked for a nested *function/arrow* boundary — so `let provider = "openai"; const setFallback = () => provider = "internal"; const model = \`${provider}/gpt-4.1\`;` was misresolved, because a concise arrow body (`() => provider = "internal"`) has no `Block` at all for the existing check to catch: the assignment sits directly under the `ArrowFunction` node, so the ancestor walk reached `SourceFile` with no conditional slot and no `Block` crossing in between, and was read as deterministic — exactly as if merely *defining* `setFallback` were the same as *calling* it. The prompt gate had the identical bypass for a `role` mutated only inside an uncalled arrow. A *braced* arrow/function already got this for free (its own body `Block` isn't `scope`, so the existing Block check alone already returns conditional) — only the braceless, concise-body case was exposed. Reproduced against current code first. Fixed by adding an explicit function-like check (`ArrowFunction`/`FunctionExpression`/`FunctionDeclaration`/`MethodDeclaration`/accessors/`Constructor`) alongside the existing Block check in `isDeterministicWrite`: any such node crossed on the way up to `scope`, other than `scope` itself, makes the write conditional. Verified the exact review case in both gates, plus a stress battery: a *braced* nested-function mutation (already worked, confirmed unaffected), a *called* function's mutation (still conservatively unioned rather than assumed-applied, since no call-graph analysis is done — the safe direction), a sequential top-level reassignment with an unrelated function declaration textually in between (still resolves to only its final value, confirming the new check doesn't over-trigger), a class method's uncalled mutation, and an array-callback (`.forEach`) mutation. Real-tree sanity check: all three gates stay clean against the real repository. `pytest tests/architecture` (70 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1025 passed) all green. | Commit. |
| 2026-09-01 | Forty-fifth round: a real GitHub Actions CI failure, not a review — the user pasted the `baseline-backend` job's log directly (`ERR_MODULE_NOT_FOUND: Cannot find package 'typescript'`, 34 tests failing on both `ubuntu-latest` and `windows-latest`). Round 43's own claim that using the `typescript` devDependency added "no new dependency" was true for the frontend workspace's own CI jobs (which already run `pnpm install`), but false for `quick-check`'s `baseline` job specifically — the one required check on every PR — which (per this file's own CLAUDE.md-documented design) deliberately never provisions the frontend toolchain at all, so the repo root's shared, pnpm-managed `node_modules/typescript` genuinely doesn't exist there. Verified the root cause directly against `.github/workflows/backend.yml`: the `baseline` job runs `uv sync` + `runner.py doctor` + `runner.py quick-check` with no `actions/setup-node`/`pnpm/action-setup` step at all, on a `[ubuntu-latest, windows-latest]` matrix. Considered and rejected two alternatives before fixing: broadening the `baseline` CI job to run `pnpm install` (rejected — cuts directly against quick-check's own explicit "no frontend checks" design, and would install the *entire* frontend workspace just for one package with zero transitive dependencies of its own); vendoring a copy of the compiled `typescript.js` bundle directly into the repo (rejected — an 8.7MB committed blob with its own manual-re-vendor-on-bump maintenance burden, when the repo already has a package manager for this). Fixed by giving `scripts/agent/` its own tiny, standalone `package.json` (pinning `typescript` alone, zero transitive deps) and having `static_string_resolution.py` self-install it via a plain `npm install` on first use — mirroring `.quick-check-venv`'s own self-management pattern exactly, including a `package.json`-hash fingerprint (written to `scripts/agent/node_modules/.quick-check-fingerprint`) so a version bump later triggers a clean reinstall instead of silently running stale, the same role `quick_check.py`'s own `dependency_fingerprint()` plays for the Python venv. This needs no CI workflow change at all: the GitHub-hosted runner images this repo's CI already uses ship Node.js and npm pre-installed with no setup step — confirmed directly by the pasted failure itself, whose error was specifically about the `typescript` *package*, not about `node`/`npm` being absent. Also wrapped both `subprocess.run` calls (`npm install`, `node js_scope_resolver.mjs`) with a clear `AssertionError` if `node`/`npm` themselves are ever genuinely missing, instead of a raw `FileNotFoundError`, and moved `node`/`npm` from `runner.py`'s `OPTIONAL_TOOLS` to `REQUIRED_TOOLS` (updating `tests/test_runner.py`'s own assertions on those lists to match) so `doctor` reports them accurately now that quick-check genuinely depends on both. Verified by deleting `scripts/agent/node_modules` (simulating the exact CI state — a fresh checkout with no prior install) and running the *actual* `runner.py quick-check` entry point end-to-end (not just pytest directly, so the real `.quick-check-venv` re-exec path and its own `runtime_env()` — confirmed to not strip `PATH` — are exercised too): the JS/TS gates correctly self-installed `typescript` on demand and all 1025 tests passed. Confirmed the standalone `package.json` correctly sits outside every `pnpm-workspace.yaml` glob (`apps/web-mirror`, `extensions/*`, `packages/frontend/*`, `tests/e2e/*`) so a root-level `pnpm install` elsewhere never touches or conflicts with it. `pytest tests/architecture` and `tests/test_runner.py` (all passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1025 passed, from a clean `node_modules` state) all green. | Commit; verify the next CI run on the actual `baseline-backend` workflow once pushed. |
| 2026-09-01 | Forty-sixth review round ("Code-review (me #34)", reviewing commit `8fb4b05`) confirmed round 44's nested-function/concise-arrow write fix holds, and found three new blocking gaps in the AST resolver's own coverage: (1) `foldExprInner` had no case for `AsExpression`/`SatisfiesExpression`/the legacy `TypeAssertionExpression`/`NonNullExpression` — TypeScript-only wrapper expressions with zero runtime effect — so `const provider = "openai" as const;` folded to nothing at all, even though `as const` is ordinary, already-used-in-this-repo syntax, not an exotic shape; (2) `var` was collected at its lexical (nearest Block) scope exactly like `let`/`const`, but real `var` is function/module-scoped and hoists out of any enclosing block — `if (enabled) { var provider = "x"; }` made `provider` invisible to a reference outside the `if`, missing an otherwise-reachable hardcode entirely — and a `for` header's own declaration (`for (let provider = "x", i = 0; ...)`) was never collected as a binding at all, since `collectDeclarations` only visited `VariableStatement`, a different AST shape than a bare `VariableDeclarationList` sitting directly in a loop's initializer slot; (3) cross-file import resolution ran as a single eager pass per file, computing and permanently memoizing each import's value at `resolveImports`-time — so a multi-hop constant chain (`a-config.ts` imports from `m-alias.ts`, which imports from `z-provider.ts`) resolved correctly only if files happened to be traversed in dependency order, since a consumer processed before its own dependency's imports were installed would memoize a stale `null`; barrel re-exports (`export { provider as MODEL_PROVIDER } from "./z-provider"`) fared worse — `ExportDeclaration` was never read into `exportedNames` at all, so importing through one couldn't resolve under any file order. All three reproduced against current code first. Fixed (1) by adding the four wrapper kinds to `foldExprInner` (each a plain unwrap of `.expression`) and to `isRootExpr`'s absorbing-parent check (so the wrapper, not its inner literal, is the one reported, avoiding duplicate `js_string_values` entries); (2) by adding `nearestFunctionScope` (walks up skipping every intervening block/for-header until a function body or `SourceFile`) and using it for `var`-flagged `VariableDeclarationList`s specifically, and by treating `ForStatement`/`ForInStatement`/`ForOfStatement` as scope nodes in their own right (mirroring how a concise arrow's own node already stands in for a body-less scope) so a `for`-header's `let`/`const` declarations can be collected and resolved from within the loop; (3) by replacing eager, single-pass import resolution with a lazy `redirect` write on the synthetic import binding — resolved on demand by a new `resolveExport` (follows `local`/`reexport`-tagged `exportedNames` entries recursively, with its own cycle guard for a circular re-export chain) and `resolveRedirectValue` (a second, decl-identity-keyed cycle guard for a genuine circular *value* dependency, distinct from a re-export cycle) — so file traversal order no longer matters at all, since nothing about "which declaration does this name resolve to" depends on any value having been folded yet; `ExportDeclaration` (both `export { a as b } from "./x"` and a bare `export { name };`) is now read into `exportedNames` as a `reexport` entry. Verified all three exact review cases, plus a stress battery: `var` two blocks deep inside a function, a `for-of` loop's own iteration variable correctly staying unresolvable (its value depends on iterating a runtime array, not an initializer — genuinely out of scope, not a bug), a `let` in a for-header correctly *not* leaking past the loop, a bare (no `from`) re-export, a deliberately-circular import pair confirmed to resolve to unresolvable without hanging (validating the new cycle guards), and a 4-hop import chain in deliberately reverse file-traversal order. Real-tree sanity check: the resolver now finds 2970 root string values across the real 145-file JS/TS tree (up from 2967 — modest, expected growth from genuinely new coverage, not a regression), runtime unaffected (~0.45s for that scan), all three gates stay clean against the real repository. `pytest tests/architecture` (79 passed), `validate_architecture.py`, `validate-docs`, and `quick-check` (1032 passed) all green. | Commit. |
| 2026-09-02 | Round 47 — another real CI failure, not a review, pasted directly by the user: the `baseline` job's `windows-latest` leg (34 tests, all in `test_no_prompts_inside_extensions.py`) failed with `AssertionError: npm is required ... but wasn't found on PATH`, while the same job's `ubuntu-latest` leg passed. Root cause: `_ensure_js_scope_resolver_dependencies()`/`js_modules()` called `subprocess.run(["npm", ...])`/`subprocess.run(["node", ...])` with bare command names and `shell=False` (the default). On Windows, `npm` ships only as `npm.cmd` (plus a `.ps1` and an extensionless POSIX shim) — no `npm.exe` — and Windows `CreateProcess` (what `subprocess` calls directly without `shell=True`) launches only the exact executable it's given; it does not apply `PATHEXT` extension search the way a shell (or Python's own `shutil.which`) does. So `"npm"` never resolved there even though it was genuinely on `PATH` (`node` itself is a real `.exe`, so it resolved fine — consistent with the failure being 100% about `npm`, never reaching the `node` call). `runner.py`'s own `probe_tool()` already sidesteps this the correct way, via `shutil.which(tool)` before invoking it; the new round-45 code didn't follow that precedent. Fixed by adding `_require_tool(name)` to `static_string_resolution.py` (thin wrapper over `shutil.which`, raising the same `AssertionError` messages as before on a miss) and resolving both `npm` and `node` through it before `subprocess.run`, matching `probe_tool`'s approach exactly; a no-op change on Linux/macOS, where `shutil.which` and bare-name resolution already agree. Did not touch `runner.py`'s own bare `["pnpm", ...]` invocations even though they have the same theoretical Windows gap — confirmed via `.github/workflows/backend.yml` that every pnpm-invoking job (`full-check`, frontend, smoke) runs `ubuntu-latest` only; only the `baseline` matrix includes `windows-latest`, and `baseline` never calls pnpm. Fixing an unexercised path on spec alone would be scope creep with nothing to verify it against. Verified by deleting `scripts/agent/node_modules` and re-running the real `runner.py quick-check` entry point end-to-end from clean (mirrors a fresh CI checkout exactly, as in round 45): self-install succeeds, `pytest tests/architecture` — 75 passed (0 failed, matching what a clean install now produces; the round-46 regressions for `as const`/`var`-in-if/for-header/import-order/barrel-reexport are all still present and passing), `validate_architecture.py` and `validate-docs` — passed, `quick-check` — 1032 passed. Can't reproduce the Windows-specific resolution failure itself on this Linux dev box, so the fix is verified by code-level correctness (mirrors `probe_tool`'s already-working approach exactly) plus full regression coverage on Linux, not by reproducing the original failure locally. | Commit; verify the next `windows-latest` CI run once pushed. |
| 2026-09-02 | Round 48 — review ("Code-review (me #35)", reviewing commit `f098c274`) confirmed rounds 46-47's fixes hold, and found two more blocking gaps, both in the resolver's own binding model rather than in any single expression-folding case: (1) `collectDeclarationList` only registered a binding when `decl.initializer` was present, so `let provider; provider = "openai";` never got a binding at all — the later plain assignment had nothing to attach its write to and was silently dropped; separately, each `var` redeclaration (`var provider = "openai"; if (x) { var provider = "internal"; }` — one runtime binding in real JS) created its own, entirely separate declaration object with its own separate `writes` array, and `resolveDecl`'s "last recorded wins" rule picked only the *last* one, discarding the earlier value's write history completely — worse, that discarded initializer had been hardcoded `own: true` (always deterministic) purely for having *introduced* the binding, regardless of its real conditional position; (2) the round-46 export resolver still missed two ordinary forms: a bare `export { name };` (no `from`) re-exporting an in-file local declaration was recorded as a *self*-pointing re-export, so `resolveExport` walked straight back into its own cycle guard (`<file>::name` already in `seen` from the very call looking it up) before ever reaching the local-declaration fallback, resolving to unresolvable for a fully static same-file re-export; and `export * from "./x"` (a star barrel) had no handling at all — `ExportDeclaration` without a named `exportClause` was simply skipped, so an import going through one couldn't resolve under any file order. All four (two sub-cases each) reproduced against current code first, standalone before any fix. Fixed (1) by splitting "create the binding" from "record a write": `FileAnalysis.addDecl` became `binding()`, a get-or-create that registers a name/scope pair with no writes at all if there's no initializer, and reuses the same object across every `var` redeclaration at the same (name, scope) instead of creating a new one each time; a declaration's own initializer write is now pushed with `own: false` (computed for real by `isDeterministicWrite`, exactly like an ordinary reassignment) instead of hardcoded `own: true` — provably the same result as before for `let`/`const` (whose own lexical scope trivially *is* wherever they're declared, so the ancestor walk always reaches `scope` immediately with nothing conditional crossed) but no longer wrong for `var`; a parameter default's write stays `own: true` unconditionally on purpose (it isn't reached through ordinary statement control flow at all — whether it applies depends on whether the caller omitted the argument, something no AST ancestor walk could see). Fixed (2) by resolving a bare (no `from`) `export { name };` directly against the file's own already-collected local declaration at `resolveImports` time instead of deferring it as a self-pointing re-export (`collectDeclarations` runs for every file before any file's `resolveImports`, so the local declaration is already there); and by recording every `export * from "./x"` in a new `analysis.starExports` array that `resolveExport` falls back to, recursively and through the same `seen` cycle guard already threading through every call, only after a direct name lookup misses. Verified all four exact review cases, plus: a deliberately circular `export * from` pair (`a.ts`/`b.ts` each star-exporting the other) resolving to unresolvable without hanging, and a genuinely nonexistent imported name through that same circular pair correctly staying unresolvable (no false positive from the new fallback). Real-tree sanity check: baseline (this round's starting commit) was 2962 root string values across the real 145-file JS/TS tree; after the fix, 2963 — a one-value increase, consistent with fixing real gaps in the safe direction (never fewer), not a regression. `pytest tests/architecture` — 81 passed (up from 75); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1038 passed, all green. | Commit. |
| 2026-09-02 | Round 49 — a third real CI failure, not a review, pasted directly by the user: `windows-latest`, two tests that scan the *real repository tree* (`test_litellm_model_strings_only_in_provider_config`, `test_no_direct_provider_api_host_references` — the only two callers of `js_modules`/`_ensure_js_scope_resolver_dependencies` that run against `ROOT`/`SCAN_ROOTS` instead of a synthetic `tmp_path` fixture) failed with `TypeError: the JSON object must be str, bytes or bytearray, not NoneType`, alongside a `PytestUnhandledThreadExceptionWarning` naming the real cause: `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 368`. Root cause: both `subprocess.run` calls in `static_string_resolution.py` (the `npm install` self-install, and the `node js_scope_resolver.mjs` call) used `text=True` with no explicit `encoding`, so Python decoded the child process's stdout/stderr using `locale.getpreferredencoding()` — cp1252 on `windows-latest`'s default English locale, not UTF-8. `js_scope_resolver.mjs` writes UTF-8 JSON containing the *full source text* of every scanned file, and this repo's own comments are prose-heavy with em/en dashes and curly quotes — real UTF-8 multi-byte sequences that happen to produce raw byte `0x90`, one of a handful of code points cp1252 leaves entirely undefined (unlike most bytes 0x80-0xFF, which cp1252 *can* decode, just to the wrong character — this one can't decode at all, so it crashed instead of merely mangling the text). Every synthetic `tmp_path` fixture across every prior round's regression tests is short, ASCII-only source, so none of them exercise real multi-byte UTF-8 output at all — only a run against the real repo tree could ever hit this. Confirmed the exact mechanism locally: `subprocess.run(["node", "-e", 'process.stdout.write(JSON.stringify({x: "‐"}))'], capture_output=True, text=True, encoding="cp1252")` raises the identical `UnicodeDecodeError: ... can't decode byte 0x90 in position 8`; the same call with `encoding="utf-8"` decodes correctly. Fixed by passing `encoding="utf-8"` explicitly to both `subprocess.run` calls — `node`'s output is unconditionally UTF-8 regardless of the host locale, so this is correct on every platform, not just a Windows-specific patch. Verified: `pytest tests/architecture` (both real-tree tests pass, 81 passed total), `validate_architecture.py`, `validate-docs`, and `quick-check` (1038 passed, from a clean `node_modules` state) all green. Can't reproduce the Windows-locale-specific crash itself on this Linux dev box, so verified by isolating and reproducing the exact underlying `UnicodeDecodeError` standalone (shown above) rather than the full CI failure. | Commit; verify the next `windows-latest` CI run once pushed. |
| 2026-09-02 | Round 50 — review ("Code-review (me #36)", reviewing commit `99e54947`) confirmed round 48's binding-lifecycle and local/star-export fixes hold, and found two more blocking false-negatives, both structural: (1) `resolveImports` only ever read `importClause.namedBindings`, so a plain default import (`import provider from "./provider"`) registered no binding at all regardless of what the source module exported; on the export side, `export default ...;` is an `ExportAssignment` — an entirely different AST node kind from `ExportDeclaration` — never read anywhere, so a default export had no entry in `exportedNames` either, and `export { default as name } from "./x"` (a named re-export of a default) inherited the same gap since it resolves through the same unregistered name; (2) a braced function's parameters were registered under `fn.body` (the function's own `Block`) as their scope — correct for references *from* the body, but a later parameter's own default-value expression (`model = `${provider}/gpt-4.1``, referencing an earlier parameter `provider`) never actually enters `fn.body` syntactically at all; its ancestor chain goes `Identifier → TemplateSpan → TemplateExpression → Parameter → FunctionDeclaration`, skipping the body Block entirely, so `nearestScope` walked straight past the function node (not itself a scope node) to whatever *encloses* the function, and an earlier parameter's binding was invisible to a later one's default. Both reproduced against current code first. Fixed (1) by reading `importClause.name` (the default import's local binding) alongside — not instead of — `namedBindings`, redirecting it to a reserved `"default"` name on the source module; and by handling `ExportAssignment` (`!node.isExportEquals`, deliberately excluding the unrelated legacy `export = x;` CommonJS-interop form) as a synthetic anonymous binding registered under that same reserved `"default"` name, whose one write is the assignment's own expression — deterministic by construction, since an `ExportAssignment` can only ever be a top-level statement; `export { default as name } from "./x"` needed no separate handling at all, since the existing named-re-export code already reads `spec.propertyName` generically as a plain string key into `exportedNames`. Fixed (2) by teaching `nearestScope` to recognize climbing up from inside a function-like node's own `parameters` array as a route to that same function's `paramOwnScope` (the exact same scope object the body already uses for its own declarations) — mirroring the pre-existing special case for a concise arrow's own body, which (being the same object as its `paramOwnScope` for a concise arrow) already handled this correctly by accident. Verified both exact review cases (provider/model and role/message), plus: a reassignment of a parameter from inside a braced function body stays correctly deterministic (unaffected regression check, since `paramOwnScope`/`fn.body` is unchanged as the actual scope object — only the *path* used to reach it from inside the parameter list changed); the legacy `export = x;` form correctly stays unmodeled (deliberately out of scope, verified it doesn't get swept in by the new `ExportAssignment` handling); a concise-arrow parameter cross-reference (already working) is unaffected. Real-tree sanity check: 2963 (this round's starting baseline) → 2972 root string values across the real 145-file JS/TS tree — a further real increase, consistent with closing genuine gaps, never a regression. `pytest tests/architecture` — 86 passed (up from 81); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1043 passed, all green. | Commit. |
| 2026-09-02 | Round 51 — review ("Code-review (me #37)", reviewing commit `24e81da9`) confirmed round 50's default-import/export and cross-parameter-default fixes hold, and found one more blocking gap in round 50's own fix: round 50 routed a parameter default's own lookup into the function *body's* `Block` scope (the same object body-local declarations use), so a body-local declaration of the same name incorrectly won lexical shadowing over a parameter default's real outer reference — real JS evaluates parameter defaults in a distinct "parameter environment" that sits *outside* the function body's own lexical environment entirely, and a body-local `const`/`let` never shadows it, no matter its textual position. Reproduced against current code first: `const provider = "openai"; function chooseModel(model = `${provider}/gpt-4.1`) { const provider = "internal"; return model; }` resolved to nothing at all (the body's own later `provider = "internal"` write wins the name lookup structurally, but its own write position is after the parameter default, so `replayWrites` found no value for it either — a silent double failure, not just a wrong value). Fixed by making the function-like node itself — not its body `Block` — every parameter's own scope: reached directly from inside the parameter list (so a body-local declaration, which lives only on the body's own `Block`, is structurally unreachable from a parameter default's lookup — there's no AST path through the body when starting inside the parameter list at all) and reached one step out from the body once nothing is found there (so the body itself still sees every parameter, exactly as real JS scoping does). While implementing this, self-caught (not part of the review) a regression it would otherwise have introduced: moving a parameter's scope off the body `Block` put that same Block *between* an ordinary body-level parameter reassignment and its own scope, which `isDeterministicWrite`'s existing Block-boundary check would misread as crossing into a conditional inner block — losing precision on a plain, unconditional `provider = "openai";` reassignment that resolved correctly before this round. Root-caused and fixed in the same change: an explicit exemption in `isDeterministicWrite` for the one case where the Block being crossed is exactly `scope`'s own `.body` (only ever true when `scope` is a parameter's function-node scope) — verified this doesn't weaken detection of a genuinely conditional reassignment (an `if`-nested one), since that case is already rejected earlier in the same walk, at the `IfStatement`/`Block` boundary, before ever reaching the function's own body Block. Verified both review cases (provider/model, role/message) plus the self-caught regression case, on function declarations, function expressions, and braced arrows alike (all three explicitly requested), plus a genuinely conditional parameter reassignment staying correctly conditional. Real-tree sanity check: 2972 root string values both before and after — unchanged, expected, since this fix only matters for a same-name shadow between an outer binding and a body-local declaration, an unlikely coincidence in real code, not a sign nothing changed. `pytest tests/architecture` — 89 passed (up from 86); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1046 passed, all green. | Commit. |
| 2026-09-02 | Round 52 — review ("Code-review (me #38)", reviewing commit `4140626d`) confirmed round 51's parameter/body scope split holds for `const`/`let` shadowing, and found one more blocking gap in the *interaction* between that scope split and `var`: a body `var` that redeclares a parameter's name creates an entirely independent, initially-empty binding in the body's own scope — but real JS (`FunctionDeclarationInstantiation`) copies the parameter's own *current* value into that same-named `var` binding at function entry, even with parameter-default expressions present, before any of the `var`'s own body-level writes run. `function chooseModel(provider = "openai") { const model = `${provider}/gpt-4.1`; var provider; return model; }` is deterministically `openai/gpt-4.1` at runtime (verified directly with `node -e`, not just reasoned about) — but the resolver picks the body's own `var provider` binding for the `model` reference (lexical lookup from inside the body finds the body scope's own `provider` first, per round 51), which has no writes at all before that position, so `replayWrites` returns empty and the reference silently resolves to nothing. Reproduced against current code first, both the no-initializer and `var provider = "internal";` variants, before any fix. Fixed by seeding a body `var`'s own `writes` array, at the moment its binding is first created, with an `own: true`, `pos: 0` entry that copies the enclosing parameter's own value (via a new `copyOf` write kind and `copyDeclValue` helper, mirroring the existing `redirect`/`resolveRedirectValue` pattern but for a same-file same-scope-tree reference, so no cycle guard is needed — only a `var` write ever carries `copyOf`, and it always points at a parameter decl, which can never itself carry one back) — found by walking from the `var`'s own scope (`nearestFunctionScope`'s returned `Block`) up one level to `.parent` (that Block's owning function node, exactly the scope round 51 gave every parameter) and looking up a same-named decl there. `pos: 0` sorts first in the write timeline regardless of where the `var` sits in the body, matching real JS's function-entry timing; a genuine explicit write on the same `var`, whether an inline initializer or a later reassignment, still correctly overrides (if unconditional) or unions with (if conditional) the seeded value through the exact same `replayWrites` machinery already in place, with no special-casing needed beyond the seed itself. Verified all three review cases (no-initializer, with-initializer, role/message) plus: a genuinely conditional `var` redeclaration of a parameter (inside an `if`) correctly keeps both the parameter's own value and the conditional redeclaration's value reachable, exactly like an ordinary conditional `var` redeclaration already does; an *unrelated*-name `var` referenced before its own declaration (no parameter of that name at all) correctly stays unresolved, matching real JS's own `undefined`-until-first-write semantics there — confirming the seed only ever fires for a genuine name collision with an enclosing parameter, not generally. Real-tree sanity check: 2972 root string values both before and after — unchanged, expected, since deliberately shadowing your own parameter with a same-named `var` is an unusual pattern unlikely to occur by coincidence in real code. `pytest tests/architecture` — 92 passed (up from 89); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1049 passed, all green. | Commit. |
| 2026-09-02 | Round 53 — review ("Code-review (me #39)", reviewing commit `d5478a6f`) confirmed round 52's copy-on-hoist fix holds for the regressions that were added, and found the deeper structural cause underneath it: `collectDeclarations` was still a single source-order traversal doing binding *registration* and write *attachment* in the same pass, so a `var`'s binding only existed once traversal physically reached its declaration statement — not real JS semantics, where a `var`'s binding (and a function's parameters) hoist to function entry regardless of where the declaration textually sits. An assignment appearing *before* its own `var` declaration therefore found no binding registered yet and either fell through to an unrelated outer scope or was silently dropped; worse, when a parameter shared the `var`'s name, that pre-declaration assignment got wrongly attached to the *parameter's* own decl (the only one that existed yet), which then leaked into round 52's `copyOf` seed — since that seed replays the parameter's timeline in full — making the "function-entry" seed actually reflect a later body assignment instead. Reproduced all three review cases against current code first — verifying the *claimed real JS runtime behavior itself* directly with `node -e` before even checking the resolver, not just trusting the review's assertion. Fixed by splitting `collectDeclarations` into two real passes: a first pass (`declare`) walks the whole file registering every lexical/hoisted-`var`/parameter binding with no writes attached to anything yet; a second pass (unchanged in structure from before) walks again in source order attaching every initializer/default/assignment write, now always finding an already-registered binding regardless of traversal order. Self-caught a second bug (not from the review) while implementing this: the round-52 `copyOf` seed, if left in the second (write-attaching) pass, checked `b.writes.length === 0` to detect "first declaration of this var" — but by the time source-order traversal reaches the `var` statement itself, a pre-declaration assignment (now correctly hoisted-and-resolved) may have *already* pushed its own write onto that same binding, making the length check see "not empty" and silently skip seeding entirely. Fixed by moving the seed into the *first* pass instead, at the exact moment the `var` binding is first created — before any write anywhere has been attached — using a dedicated freshness check (no writes exist at that point for anyone), and relying on `copyOf` being a lazy reference to the parameter's decl *object* (not a value snapshot), which only needs that object to already exist, not yet its own write (guaranteed by the pre-order walk visiting a function's parameters before recursing into its body). Verified all three review cases, then re-verified every prior round's own regression case (37 through 52, the full parameter/`var`/scope-split history) produces byte-identical output to before this round — no regression anywhere in that chain. Real-tree sanity check: 2972 root string values both before and after — unchanged, expected, since assignment-before-declaration is an unusual pattern unlikely to occur in real code. `pytest tests/architecture` — 95 passed (up from 92); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1052 passed, all green. | Commit. |
| 2026-09-03 | Round 54 — review ("Code-review (me #40)", reviewing commit `a34b0458`) confirmed round 53's hoisting-order fix holds, and found `isDeterministicWrite`/`isConditionalSlot` never recognized short-circuit (`&&`/`||`/`??`) or ternary (`?:`) conditional *expression* evaluation at all — only conditional *statement* control flow (`if`/loop bodies/`try`/`switch`). `useFallback && (provider = "internal");` never runs the assignment at all when `useFallback` is falsy, exactly like an `if` body that might not run, but the write's ancestor walk (assignment → parenthesized expression → `&&` binary expression → expression statement → source scope) never crossed anything `isConditionalSlot` recognized, so the write replaced the reachable `"openai"` value with `"internal"` instead of joining it — a real false negative, not just an imprecision, since the *deterministic* branch of `replayWrites` discards prior values entirely rather than accumulating them. Reproduced both `&&` and ternary forms against current code first (both showed only `internal/gpt-4.1` reachable, missing `openai/gpt-4.1` completely), then confirmed `||`, `??`, and the prompt-role equivalent all shared the identical gap, before fixing anything. Fixed by adding two checks to `isConditionalSlot`: a `BinaryExpression` whose `.right` is `node`, gated by the actual operator kind (`&&`/`||`/`??` only — a plain `BinaryExpression.right` is otherwise perfectly ordinary, e.g. `+`'s right side always evaluates unconditionally, so this can't be a blanket AST-shape match the way the loop/if slots are), and a `ConditionalExpression` whose `whenTrue` or `whenFalse` is `node`. Verified all three review-named forms (`&&`, ternary, role/message) plus `||`/`??` directly, and — critically — that an ordinary `+` concatenation (`"open" + "ai"`) is *not* newly misclassified as conditional by the operator-kind gate (still resolves to a single deterministic `openai/gpt-4.1`, unaffected). Real-tree sanity check: 2972 root string values both before and after — unchanged, expected, since a short-circuit/ternary reassignment is an unusual pattern unlikely to occur in this repo's own real code. `pytest tests/architecture` — 98 passed (up from 95); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1055 passed, all green. | Commit. |
| 2026-09-03 | Round 55 — a fourth real CI failure, not a review, pasted directly by the user: `runner.py doctor` on `windows-latest` reported `Required tool is unavailable: npm`, with the detail `unusable (Command '[...npm.CMD, --version]' timed out after 10 seconds)` — `node --version` resolved fine on the same run. Root cause: `npm` is itself a Node.js process under the hood, and a well-documented Node/Windows quirk (`nodejs/node#10836`, confirmed via web search before touching any code, not assumed) makes `process.stdin` access hang when its stdin handle is inherited from a non-interactive parent — a CI runner's own stdin — without ever being explicitly closed, even for a command that never actually reads input. `probe_tool`'s `subprocess.run` call (and the round-45 self-install's own `npm install` call) left `stdin` unset, so both inherit whatever the caller's stdin is; `node --version` was unaffected because `node` itself is a real `.exe` with no npm-CLI-level Node-process-startup stdin touches to trigger the quirk. Fixed by passing `stdin=subprocess.DEVNULL` to both calls — the `node ...` call that pipes the file list in via `input=...` was already safe (Python's `input=` parameter creates and closes its own stdin pipe automatically), so it needed no change. Verified locally (Linux, can't reproduce the Windows-specific hang itself): `runner.py doctor` still correctly reports `npm`/`node` with `stdin=subprocess.DEVNULL` set; deleted `scripts/agent/node_modules` and re-ran the real `runner.py quick-check` entry point end-to-end — self-install and all gates still work identically with stdin closed. `pytest tests/test_runner.py` — all passed; `validate_architecture.py`, `validate-docs`, and `quick-check` — 1055 passed (unchanged count — this round added no new resolver behavior or tests, only a subprocess-invocation fix), all green. | Commit; verify the next `windows-latest` `doctor` run once pushed. |
| 2026-09-03 | Round 56 — review ("Code-review (me #41)", reviewing commit `8b129145`) confirmed round 54's short-circuit/ternary fix holds, and found three related write-semantics gaps, all in how a write's own RHS is resolved: (1) compound assignment operators (`+=`, `||=`, `&&=`, `??=`) were never recorded as writes at all — the collector only matched a plain `=` `EqualsToken`; (2) a genuinely self-referential ordinary reassignment (`provider = provider + "ai";`) *was* collected, but resolving the RHS's own `provider` reference used that reference's own literal text position (always textually *after* the assignment's LHS, since the RHS is written after `provider =`) as the replay cutoff — which always included this exact not-yet-applied write itself, hit `foldExpr`'s cycle guard, and lost the value entirely rather than resolving against the pre-write state; (3) self-caught while implementing (1) with a stress test, not part of the review: a nested assignment inside a *compound* logical assignment's own RHS (`enabled &&= (provider = "internal")`) wasn't recognized as conditional either, since round 54's `SHORT_CIRCUIT_OPERATORS` set only listed the plain operator tokens (`&&`/`||`/`??`), not their compound-assignment forms (`&&=`/`||=`/`??=`) — the exact same short-circuit, on the exact same AST shape (`BinaryExpression.right`), just a different operator token. Reproduced all three review-named cases against current code first (all three showed the wrong or entirely missing value), then discovered (3) via a stress test of the just-implemented fix, before writing any test for it. Fixed (2) — the deepest one — with a purely *structural* fix, not a transient/order-dependent one: `selfReferenceContext(node, decl)` walks a reference's ancestors checking whether it sits inside one of `decl`'s own write expressions; if so, that write's own position (excluding the write itself, via a new `excludeWrite` parameter on `replayWrites`, needed because an equal position isn't excluded by the existing `pos > atPos` cutoff alone) becomes the replay cutoff instead of the reference's own literal position — deliberately structural rather than a transient "currently resolving this write" override, since `foldExpr`'s permanent per-node memoization means whichever caller folds a node *first* (not necessarily the "intended" one — the generic every-node scan in `main()` reaches the same nodes independently of any per-write override) fixes that node's value forever, so a fix that depended on call order would silently not apply whenever the generic scan won the race. Fixed (1) by recording `+=` writes with a `compoundOp` marker resolved via `replayWrites` calling itself for the pre-write state (reusing the very same self-reference machinery from (2)) then `combine`-concatenating with the folded RHS, and `||=`/`&&=`/`??=` writes with a `forceConditional` marker — the write's own contribution is just the folded RHS, always joined into the reachable set rather than replacing it, since the old value's survival when the operator doesn't trigger is already implied by not replacing (identical reasoning to round 54's plain short-circuit fix). Fixed (3) by adding the three compound-assignment operator tokens to the existing `SHORT_CIRCUIT_OPERATORS` set. Verified all three review cases, the self-caught one, a 3-hop self-referential reassignment chain (`"op"` → `+"en"` → `+"ai"`), and confirmed a plain `+` concatenation is still unaffected. Real-tree sanity check: 2972 → 2977 root string values — a real, larger-than-usual increase for this chain of rounds, consistent with self-referential reassignment and compound operators being ordinary, common patterns this repo's own code actually uses (unlike some of the more exotic prior-round fixes, whose real-tree count stayed flat). `pytest tests/architecture` — 103 passed (up from 98); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1060 passed, all green. | Commit. |
| 2026-09-03 | Round 57 — review ("Code-review (me #42)", reviewing commit `49687d3b`) confirmed round 56's compound-assignment/self-reference fix holds, and found the first binding pass only ever registered a function parameter as a binding when it had a *default value* — `function chooseModel(provider) { provider = "openai"; return \`${provider}/gpt-4.1\`; }` never registered `provider` at all, so the later deterministic assignment had nowhere to attach and was silently dropped. Worse than a missed hardcode: since a non-default parameter is a real lexical binding that shadows any same-named outer variable for the whole function, an *unregistered* one let a reference inside the function fall straight through to an outer same-named binding instead — reproduced and confirmed this second, more severe shape myself before touching any code (`const provider = "openai"; function chooseModel(provider) { return \`${provider}/gpt-4.1\`; }` incorrectly resolved the parameter's own reference to the *outer* constant's value, a genuine false positive claiming a specific value a caller-provided, genuinely dynamic parameter never actually has — not merely an imprecision in the safe direction like most of this resolver's other known ceilings). Fixed by registering every identifier parameter in the first (binding-existence) pass unconditionally, dropping the `&& param.initializer` guard that previously gated registration entirely; the second (write-attaching) pass already only attached a *default-value write* when `param.initializer` exists, so no change was needed there — reusing the now-already-registered binding is exactly the "parameter exists → binding; parameter has initializer → additionally attach default-value write" split the review asked for. Verified both cases (deterministic assignment now resolves; shadowing now correctly resolves to *nothing* rather than the wrong outer value), plus the existing `test_non_default_role_parameter_is_not_a_false_positive` (correctly still passes, confirming no regression on the no-conflicting-outer-binding case it does cover) and confirmed it does *not* exercise real shadowing, exactly as the review said — added the missing coverage rather than relying on that existing test alone. Real-tree sanity check: 2977 root string values both before and after — unchanged, expected, since a deterministically-assigned non-default parameter or a parameter deliberately shadowing a same-named outer constant are both narrow patterns unlikely to occur in this repo's own real code. `pytest tests/architecture` — 107 passed (up from 103); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1064 passed, all green. | Commit. |
| 2026-09-03 | Round 58 — review ("Code-review (me #43)", reviewing commit `1be4400e`) confirmed round 57's non-default-parameter fix holds, and found the resolver had no model at all for static member access: `foldExprInner` had no case for `PropertyAccessExpression`/`ElementAccessExpression`, and `resolveImports` only ever read `ImportClause.name`/`NamedImports`, never `NamespaceImport` — so `import * as providers from "./providers"; ...providers.primaryProvider...` and a fully static `config.primaryProvider` (`config = { primaryProvider: "openai" }`) were both invisible, since neither half (the namespace/object binding, nor the property-access expression reading it) had any resolver support whatsoever. Reproduced all three review-named cases against current code first, plus `ElementAccessExpression` with a static string key (`config["primaryProvider"]`, explicitly requested as a related hole in the same message even though not in the three named regression cases). Fixed with two new pieces: `resolveObjectLiteral(analysis, expr)` — deliberately narrow, structural, single-value resolution (an inline object literal, or an identifier with *exactly one* write whose own expression is an object literal after unwrapping transparent TS wrappers) that answers only "is this *always* this one specific object literal," never attempting the full conditional/union value-set tracking `replayWrites` does for strings, since an object's shape isn't a small combinatorial set of possibilities the way a folded string is; and `resolvePropertyAccess(analysis, objExpr, propName)`, which resolves either through a `NamespaceImport` binding (tagged with a new `namespaceOf` field pointing at the source module's analysis, looked up via the existing `resolveExport`/`replayWrites` — reusing the exact same module-export-graph machinery an ordinary named import already uses) or through `resolveObjectLiteral`'s result, looking up a non-computed property (or shorthand) by name. Wired into `foldExprInner` for both `PropertyAccessExpression` and `ElementAccessExpression` (the latter only when the index is a static string literal — a computed key, `config[key]`, has nothing statically knowable to look up). Verified all three review cases, `ElementAccessExpression`, and two deliberate non-resolution checks: a dynamic (`config[key]`) index and a `let` reassigned to a second object literal both correctly stay unresolved rather than guessing — confirming the narrow, single-value design holds its safe-direction guarantee. Two of the new regression tests needed fixture rework after landing: an object literal's own `role: "system"`-shaped property coincidentally matched the pre-existing *text-level* system-role-shape fallback regex independent of the new property-access feature (the regex has no word-boundary anchor, so even a key merely *ending* in "role", like `defaultRole`, matched too) — reworked to a property name (`preset`) that isolates what the test actually exercises. Real-tree sanity check: 2977 → 2997 root string values — a notably larger jump than most rounds in this chain, since property access on an object literal or module namespace is an extremely common real-world pattern, unlike several of the narrower prior-round fixes whose real-tree count stayed flat. `pytest tests/architecture` — 114 passed (up from 107); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1071 passed, all green. | Commit. |
| 2026-09-03 | Round 59 review ("Code-review (me #44)") explicitly labeled itself "repeat review: there are no new commits since the previous review — the PR head is still `1be4400e`" and restated round 58's namespace-import/object-property finding verbatim. `1be4400e` is round 57's commit, not round 58's — the review ran against a commit one round stale, because round 58's fix (committed locally) had never been pushed to `origin/feature/ANY-25`, so whatever the review process reads (the PR/remote head) genuinely had no new commits from its point of view; the finding wasn't wrong when written, just answered by work the reviewer couldn't see yet. Reverified all three of the review's exact repro cases directly against current HEAD (not assumed stale from the commit hash alone): the namespace-import provider case, the namespace-import role case, and the local-object-literal case all already resolve correctly. No code changes made — nothing to fix. `pytest tests/architecture` (114 passed) reconfirmed green, no regression. | Push local commits so the next review sees current HEAD; otherwise none — awaiting a review against a pushed commit. |
| 2026-09-03 | Round 60 — review ("Code-review (me #45)", reviewing commit `ff012ce0`) confirmed round 58's namespace-import/object-literal fix holds for immutable object contents, and found round 58's own safety check confused two different questions: `resolveObjectLiteral`'s `decl.writes.length !== 1` guards against the object *binding* being rebound to a different literal (`let config = {...}; config = {...};`), but says nothing about that object's *properties* being mutated after construction — `config.primaryProvider = "openai";` (a `PropertyAccessExpression` on an assignment's LHS) was never collected as a write anywhere at all, since the assignment-collecting code only matched a plain identifier LHS, so the resolver kept treating a property as permanently equal to its object literal's own initializer even after an ordinary, deterministic mutation overwrote it — a real false negative, not merely an imprecision. Reproduced against current code first, confirming the resolver returned the pre-mutation value even though the mutation was a plain top-level statement with nothing conditional about it. Fixed with a genuine per-property write timeline rather than a "give up once mutated" fallback (the review offered both; the timeline serves the gate's actual purpose — catching the real hardcode — while a blanket refusal would only prevent a wrong answer, not produce a right one for the review's own named case): `getOrCreatePropertyDecl(analysis, objectDecl, propName)` creates a binding-shaped decl stored directly on the object's own decl object (properties aren't part of any lexical scope chain, so they can't live in `declsByScope` the normal way), seeded once on first creation with the object literal's own initializer for that property (`own: true`, exactly like a declaration's own initializer or a parameter default) if one is found via `objectLiteralFromDecl` (the renamed, decl-taking half of round 58's `resolveObjectLiteral`); a new branch in the pass-2 assignment walk collects `obj.prop = ...`/`obj["prop"] = ...` mutations onto this same per-property timeline, `own: false`, with `propDecl.scope` copied from the object binding's own scope so `isDeterministicWrite` has a real scope node to walk toward — reusing the exact same `replayWrites`/`isDeterministicWrite` machinery every other binding already goes through, rather than inventing a parallel value model just for object properties. `resolvePropertyAccess` now threads the reference's own position through to `replayWrites` (previously ignored, since nothing before this needed it), so a reference *before* a later mutation correctly sees only the pre-mutation value — real JS temporal order, not "any write anywhere in the file." Verified all three review cases (property mutation, static element-assignment mutation, prompt-role property mutation), plus self-directed stress tests: a mutation inside an `if` correctly unions with the object's original value rather than replacing it (mirroring how an ordinary conditional variable reassignment already behaves), and a mutation positioned *after* the read site correctly does not apply retroactively. Two of the five new regression tests needed a fixture fix after first landing: `LITELLM_MODEL_STRING_RE` only matches a curated `LITELLM_PROVIDERS` allowlist, and "internal" (the placeholder used for the object's *pre-mutation* value) isn't in it, so the gate's own regex silently never matched that half of the fixture regardless of the resolver being correct — switched to "custom" (a real list entry) so the test could actually observe what it was trying to test. Real-tree sanity check: 2997 → 3004 root string values — a real, modest increase. `pytest tests/architecture` — 119 passed (up from 114); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1076 passed, all green. | Commit. |
| 2026-09-03 | Round 61 — review ("Code-review (me #46)", reviewing commit `7287775f`) confirmed round 60's object-property-mutation fix holds, and found both declaration passes skipped any `decl.name` that wasn't a plain `Identifier` outright, so `const { provider } = config;` (an `ObjectBindingPattern`) and `const [primary] = providers;` (an `ArrayBindingPattern`) registered no binding at all — a very ordinary destructuring pattern, not an exotic one. Reproduced the object-destructuring, aliased-destructuring (`{ primaryProvider: provider }`), and the review's own explicitly-called-out "opposite failure mode" (a destructured parameter shadowing a same-named outer constant, confirmed by direct repro before fixing — exactly the round-57 non-default-parameter shape recurring on a new binding kind) against current code first. Fixed by making declaration collection genuinely recursive over `BindingName` instead of gating on `ts.isIdentifier`: a new `declareBindingName` (first pass) registers every leaf identifier in an arbitrarily-nested pattern, including through rest elements (`...rest` is itself a plain-identifier leaf, registered like anything else) and skipping only an omitted array slot (`[, b]`, which names nothing); a new `attachBindingPatternWrites` (second pass) attaches a `destructureFrom` write to each *directly-named* leaf (`kind: "object"` with a property name, or `kind: "array"` with an index), resolved lazily by a new `replayWrites` branch that calls `resolvePropertyAccess` (object case — deliberately reusing round 60's mutation-aware, position-aware machinery unchanged, so a destructured value taken *at this statement's own position* correctly reflects an earlier property mutation and never a later one) or a new `resolveArrayElement` (array case — direct structural lookup only, no mutation tracking, mirroring how object-property resolution itself started in round 58 before round 60 added a write timeline; array mutation — `push`/`splice`/index-assignment/`length` — is a much larger, unrequested surface). Deliberately scoped narrower in two explicit places, both documented in code rather than left as accidental gaps the way round 58's property-mutation gap was: a *nested* pattern (`const { a: { b } } = x;`) recurses for registration (correct shadowing) but not value resolution, since there's no real AST node representing "the value of the outer `a` slot" a further extraction could target; and a rest element is registered but never given a value, since "everything except these named properties" has no static value model here at all. Verified all three review-named cases, the shadowing case, array destructuring, a rest element (no crash, no false resolution for `rest` itself, `provider` still resolves normally), and a destructured value correctly reflecting an earlier (not later) property mutation of its source — reusing round 60's `atPos`-aware `resolvePropertyAccess` directly. All 6 new regression tests passed on the first run, with no line-number or fixture-shape corrections needed this round (unlike several prior rounds). Real-tree sanity check: 3004 → 3014 root string values — a real, modest increase. `pytest tests/architecture` — 125 passed (up from 119); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1082 passed, all green. | Commit. |
| 2026-09-03 | Round 62 — review ("Code-review (me #47)", reviewing commit `2754ed30`) found the round-61 recursive `BindingName` handling was applied only to variable declarations: the function-parameter branch kept its own `isIdentifier` guard, so a destructured parameter (`function chooseModel({ provider })`) still created no binding — the same root cause one collection path over, including the round-57 shadowing false positive recurring on it. Rather than close that one path and wait for the next review to find the next one, this round enumerated *every* place a JS/TS binding is born and every still-fixable documented ceiling, and closed them all at once, each verified by a standalone repro before and after: (1) parameters of *every* function-like kind — the old branch listed only declarations/expressions/arrows, so class methods, accessors, and constructors never registered their parameters either — now recurse through `declareBindingName`, with a defaulted destructured parameter (`{ provider } = { provider: "openai" }`) attaching writes via the same `attachBindingPatternWrites` a declaration uses; (2) catch-clause variables, function-declaration names, class/enum/namespace names — bindings that had never been registered, so each could let a reference fall through to shadow a same-named outer binding; (3) nested destructuring (`{ a: { b } }`) now resolves through every level via a member-key `path`, and a per-element default (`{ provider = "openai" }`) applies when — and only when — the key is *provably* absent from a fully known source (`memberStaticallyAbsent`; an unknown source stays unresolved rather than guessing); (4) object spread (`{ ...base, x }`, walked in reverse so a later member wins, as at runtime), numeric index reads/mutations (`arr[0]`, sharing the object-property write timeline under the key `"0"`), and compound mutations on a member (`obj.prop += "x"`, `||=` etc.); (5) TS `enum` members, `namespace` members (its `ModuleBlock` is now a scope node), and class `static` members — the "class members" ceiling and its two adjacent TS container kinds — all through one `literalMember` lookup feeding the same `getOrCreatePropertyDecl` timeline, so `Config.provider = "openai"` overrides a static initializer exactly like an object property. Self-caught while stress-testing: a destructuring alias *key* (`{ primaryProvider: provider }`) was folded as if it were a variable reference, reporting an unrelated outer binding's value at the key position — traced to `main()`'s every-node pass folding every identifier regardless of `isIdentifierReference` (which only gated the second pass); fixed by merging the passes and skipping non-reference identifiers, which also removed the older "declaration name resolves to its own initializer" duplicate-position quirk noted back in round 56. Verified the 19-case battery, then the full regression suite; all 19 new regression tests (16 LiteLLM, 3 prompt-gate) passed on the first run with no line-number or fixture corrections. Real-tree sanity check: 3014 → 2985 root string values — a *drop*, the one direction that could hide a real loss, so verified precisely rather than assumed: the set of (file, value) pairs is identical before and after (1766 = 1766, zero lost, zero gained); the decrease is entirely duplicate positions of the same values that declaration-name folding used to produce. Deliberately still not modeled, and documented rather than left silent: a rest element's value, a nested pattern's intermediate-level default, array mutation beyond a direct index write (`push`/`splice`/`length`), computed keys, instance/prototype class members, `export * as ns`, and the Python resolver's conditional-branch module-constant gap (single-value model; a separate subsystem no review has raised). `pytest tests/architecture` — 144 passed (up from 125); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1101 passed, all green. | Commit. |
| 2026-09-03 | Round 63 — review ("Code-review (me #48)", reviewing commit `2d8a5ea7`) confirmed round 62's parameter/binding fixes hold, and found `resolveDestructuring` used the mutation-aware property timeline only for the *final* segment of a nested pattern's path — every intermediate segment did a structural `literalMember` lookup against the container's *original* literal, so `config.llm = { provider: "openai" }` (stored on the `llm` property timeline, not as a rebinding of `config`) was invisible to `const { llm: { provider } } = config`. Reproduced against current code first, then reproduced the whole sibling class before fixing anything: a chained `config.llm.provider` read, a nested member write `config.llm.provider = ...`, a spread from a mutated base, a property compound self-reference, a class static replaced then read through, an intermediate-level destructuring default, rest elements, and computed keys all either read the stale literal or resolved to nothing (20-case battery, every case wrong or empty). Root cause is structural, not one missing branch: rounds 58–62's member model was a per-property write timeline hung off a *single-shape* container (`containerLiteralFromDecl`), so any read that crossed a container replaced since construction had nowhere to go but the original literal. Replaced the entire member layer with one path model: every read is `(root binding, key path, position)` (`exprValues` flattens `a.b[c]` into `a` + `["b", "c"]`, a destructuring is the same path at the pattern's own position), every member assignment at any depth is a write on the *root* binding carrying its access chain (`decl.memberWrites`; keys resolved lazily by `memberKeys`, so `config[KEY] = ...` with a foldable `KEY` matches exactly, an ambiguous key matches conditionally, and an unknown key is a possible overwrite of any slot — the safe direction for a gate), and one `replayPath` merges the binding's own writes with every member write on a prefix of the path, in source order, walking a shallower write's new value structurally the rest of the way (`literalValues`: object props in reverse, spread read *through* to its source, array index, class static, computed keys that fold). Captured-reference semantics (`ctx.bindPos`/`refDepth`) make JS's reference model explicit: a value reached through a literal member, a destructured object, or a spread was *bound* at one position and *copied* to a known depth, so a later rebinding/replacement at or above that depth no longer concerns the object this read holds (a conditional one only makes what follows uncertain), while a later mutation *below* that depth — of the shared object itself — still does. Verified with a second 22-case battery whose expected values come from actually running each fixture under `node`, not from reasoning: every case is exact or a safe superset (a union where the runtime picks one branch), including alias mutation through a literal, rebinding after capture, spread copy-vs-shared-nesting, destructured object vs destructured string snapshots, and a chain read through an import. Self-caught while landing: `export default provider;`'s synthetic write sat at position 0, which the new capture rule read as "the real declaration came after the capture" and dropped the value — one existing regression caught it; fixed by giving that write its real position. Real-tree sanity check, diffed exactly: 0 `(file, value)` pairs lost, 1 gained (`process.env.X ?? "http://localhost:18000"` — a `??` fallback now correctly reachable), 2985 → 3015 root entries (ternary/short-circuit branches now each report). `pytest tests/architecture` — 172 passed (up from 144: 25 LiteLLM-gate + 3 prompt-gate regressions, covering every reviewer-requested case — before/after the destructuring, the nested role case — plus every sibling above); `validate_architecture.py`, `validate-docs`, and `quick-check` — 1129 passed, all green. | Commit. |

## Open questions

- None.

## Follow-up debt

- None. (Round 24's deferred temp-tree regression fixtures landed in round 34: every gate is a
  `check_*(root, ...)` function with isolated `tmp_path` regressions.)
- Round 43 replaced the entire JS/TS side of the shared resolver with a real TypeScript-compiler
  parse (`scripts/agent/js_scope_resolver.mjs`), so every JS/TS ceiling accumulated across rounds
  34-42 (flat namespace, any-reassignment-invalidates, deterministic-only-overrides, `{}`-depth-
  only conditional detection, unmodeled concise-arrow parameter defaults, ASI/comma/bracket-close
  scope leaks, object-literal commas) is closed — most as a direct consequence of using a real
  parser, not as a targeted fix; verified in-session that this also closed two things never even
  reported as bugs (the `do`-loop braceless-body ceiling, and round 42's own just-documented
  remaining ceiling). The few ceilings that remain are all *new*, narrower, and specific to the
  real-parser implementation itself (`ponytail:` comments in `js_scope_resolver.mjs` and
  `static_string_resolution.py`): destructuring declarations (`const { a, b } = obj`) and a
  `for (let i = ...; ...)` loop's own init declaration aren't modeled as bindings at all (neither
  was under the old resolver either — not a regression); JS/TS `var`'s real function scope is
  still approximated as block scope (narrower — can only miss an in-scope `var`, never resolve
  one that isn't); a Cartesian-product combine caps at 256 possible values per expression rather
  than doing unbounded path-sensitive analysis (a real hardcode fed by more than a couple of
  conditional branches in one expression is vanishingly unlikely, and would very likely also be
  reachable through a simpler branch elsewhere); only a direct `import { NAME } from "./x"`
  (relative specifier, named import) resolves cross-file — a re-export (`export { NAME }`) or
  `export default` isn't followed; only bare `${NAME}` template holes fold; and — no call-graph
  analysis is done at all, deliberately — a write inside *any* function/arrow, called or not,
  resolves as merely conditional (unioned, never assumed-applied) rather than tracking whether
  the call genuinely precedes the use site, which can only ever widen the reachable set, never
  narrow it incorrectly (round 44 closed the one way this used to go wrong instead: an uncalled
  function's write being wrongly read as unconditionally applied). Upgrade path for all of them,
  if ever needed, is extending the same real-AST script rather than adding more character-level
  heuristics. Python's own module-constant resolution has a parallel, currently
  unreported gap: `_add_module_level_constants` only scans `tree.body`, so an assignment inside a
  conditional branch (`if cond: NAME = "x"`) is invisible rather than wrongly resolved — safe in
  direction (never a wrong value) but doesn't track a conditionally-reachable value as *also*
  reachable the way the JS/TS side now does; not fixed here since no review round has raised it
  for Python, and the Python resolver stays AST-based (`ast`), unaffected by round 43's change.
- Round 45: none remaining. The `typescript` dependency round 43 introduced now installs itself
  (via `scripts/agent/package.json` + a self-triggered `npm install`, fingerprinted the same way
  `.quick-check-venv` is), so quick-check's `baseline` CI job needs no workflow change and no
  frontend-workspace provisioning to run the JS/TS gates. Verified end-to-end against the actual
  `runner.py quick-check` entry point (not just pytest directly) from a deleted-`node_modules`
  state, matching a fresh CI checkout exactly.
- Round 46 closed four of the ceilings round 43 had listed as remaining: `as const`/`satisfies`/
  legacy-cast/`!` are now unwrapped before folding instead of dropping the wrapped value; `var`'s
  real function/module scope is now modeled via `nearestFunctionScope` instead of approximated as
  block scope; a `for` header's own `let`/`const`/`var` declaration list is now collected (the
  `for`-statement node itself is a scope node); and cross-file resolution now follows a re-export
  (`export { NAME } from "./x"`, including renamed and bare `export { NAME };`) via `resolveExport`,
  not just a direct named import, with its own cycle guard separate from the circular-value-
  dependency guard added for the now-lazy `redirect` writes. Still open, narrower than before:
  destructuring declarations (`const { a, b } = obj`) still aren't modeled as bindings; the 256-
  combination Cartesian-product cap; no call-graph analysis (unchanged rationale from round 43);
  `export default` still isn't followed; only bare `${NAME}` template holes fold. Python's
  conditional-branch module-constant gap (line ~1676) is also unaffected by this round.
- Round 47: none remaining. The `npm`/`node` bare-name resolution gap round 45's self-install
  introduced on `windows-latest` is closed — both tools are now resolved through `shutil.which`
  before invoking, matching `probe_tool`'s existing approach. `runner.py`'s own bare `["pnpm", ...]`
  calls have the same theoretical gap but are unexercised on Windows in CI today (only the
  `baseline` job's matrix includes `windows-latest`, and `baseline` never calls pnpm) — left as-is
  rather than fixed on spec with nothing to verify it against; worth revisiting only if a pnpm-
  invoking job is ever added to the Windows leg.
- Round 48 closed the last major structural gap in the binding model: an uninitialized declaration
  (`let x;`) now registers a real binding a later assignment can attach to; every `var`
  redeclaration at the same name/scope now contributes to one shared binding instead of each
  silently discarding the last one's write history, with its own initializer's determinism
  computed for real (`isDeterministicWrite`) instead of hardcoded true; a bare same-file
  `export { name };` now resolves directly instead of self-cycling to unresolvable; and
  `export * from "./x"` is now followed via a `starExports` fallback. Still open, unchanged from
  round 46: destructuring declarations (`const { a, b } = obj`) aren't modeled as bindings; the
  256-combination Cartesian-product cap; no call-graph analysis; `export default` isn't followed;
  only bare `${NAME}` template holes fold; Python's conditional-branch module-constant gap.
- Round 49: none remaining. The cp1252-decode crash round 45's self-install exposed on
  `windows-latest`'s real-tree tests is closed — both `subprocess.run` calls now pass
  `encoding="utf-8"` explicitly, correct on every platform since `node`'s own output is
  unconditionally UTF-8 regardless of host locale.
- Round 50 closed two of the items round 48 had left open: `export default`/default imports are
  now followed (a default import redirects to a reserved `"default"` export-map name; `export
  default <expr>;` registers a synthetic anonymous binding under that same name), and a braced
  function's later parameter default can now see an earlier parameter's binding. Still open,
  unchanged from round 46: destructuring declarations (`const { a, b } = obj`) aren't modeled as
  bindings; the 256-combination Cartesian-product cap; no call-graph analysis; only bare `${NAME}`
  template holes fold; Python's conditional-branch module-constant gap; the legacy `export = x;`
  CommonJS-interop form is deliberately not modeled as a default export (verified it doesn't get
  swept in by round 50's `ExportAssignment` handling).
- Round 51 closed the scope-isolation gap round 50's own fix introduced: a parameter default no
  longer resolves a same-named body-local declaration instead of its real outer binding, since
  every parameter's own scope is now the function node itself rather than its body `Block`. Also
  closed, self-caught rather than review-reported: `isDeterministicWrite` no longer misreads a
  plain, unconditional parameter reassignment from directly inside the body as merely conditional
  — a precision regression round 51's own scope change would otherwise have introduced. No other
  items from round 48's still-open list changed this round.
- Round 52 closed the interaction gap between round 51's parameter/body scope split and `var`: a
  body `var` redeclaring a parameter's name now inherits that parameter's own value at function
  entry (matching real JS), instead of starting as an independent, initially-empty binding that
  silently hid the parameter's real value from any reference preceding the `var`'s own first
  write. No other items from round 48's still-open list changed.
- Round 53 closed the true root cause underneath round 52's fix: binding registration is now a
  genuine first pass over the whole file, independent of write attachment, so a `var`'s binding
  (and a function's parameters) exist from function entry exactly like real JS hoisting, regardless
  of where the declaration sits textually — an assignment before its own `var` declaration now
  always resolves to that binding, never falls through to an outer scope or gets silently dropped,
  and never leaks into a same-named parameter's `copyOf` seed. No other items from round 48's
  still-open list changed.
- Round 54 closed a class of gap distinct from every one before it in this chain: all of rounds
  36-53 were about *statement*-level control flow or *binding* structure; round 54 is the first
  about conditional *expression* evaluation specifically — a write behind `&&`/`||`/`??`'s
  short-circuited side or an untaken ternary branch is now correctly joined into the reachable set
  instead of replacing it, matching every other conditional-write case already handled. No other
  items from round 48's still-open list changed.
- Round 55: none remaining. The Windows `npm --version`/`npm install` stdin-inheritance hang is
  closed — both calls now explicitly pass `stdin=subprocess.DEVNULL`, correct on every platform
  since a closed stdin never changes behavior for a command that doesn't read input on any OS.
- Round 56 closed the write-semantics gaps around compound assignment operators and
  self-referential reassignment: `+=`/`||=`/`&&=`/`??=` are now recorded and resolved correctly,
  a self-referential RHS resolves against the real pre-write state instead of losing its value to
  the fold cycle guard, and a nested assignment inside a compound logical assignment's own RHS is
  now correctly conditional. Other compound operators (`-=`, `*=`, `/=`, etc.) remain unmodeled —
  not requested, and arithmetic on strings has no meaningful string-hardcode-gate relevance the
  way `+=`/`||=`/`&&=`/`??=` do. No other items from round 48's still-open list changed.
- Round 57 closed a real correctness gap that had existed since parameters first got their own
  scope (round 51): a non-default parameter is now a real binding from function entry, exactly
  like a defaulted one, so it both accepts a later deterministic assignment and correctly shadows
  a same-named outer binding instead of silently falling through to it. No other items from round
  48's still-open list changed.
- Round 58 added a genuinely new capability, not just closed an existing ceiling: static member
  access (`.property`/`["static-key"]`) through a namespace import or a fully static local object
  literal. Deliberately narrow, matching the review's own ask rather than over-building: only a
  *single-write* object-literal binding resolves at all (a `let` reassigned to a second literal, or
  one with more than one write, correctly stays unresolved rather than guessing which); only a
  *static string-literal* element-access key resolves (`config[key]` stays unresolved); computed
  property names, `export default` namespace access, and class members are all still unmodeled —
  none requested, and each is a narrower, separate extension of the same machinery if ever needed.
- Round 60 closed the mutation-tracking gap round 58's own single-write check left open: a property
  is no longer treated as permanently equal to its object literal's own initializer once a direct
  static mutation exists. Still open, matching round 58's own listed ceilings: computed property
  names, `export default` namespace access, class members, and compound-operator mutations on a
  property (`obj.prop += "x"`) — none requested, narrower extensions of the same now-established
  per-property write-timeline machinery if ever needed.
- Round 61 closed the destructuring gap: object and array binding patterns are now real bindings,
  correctly shadowing, with a one-level-deep value resolved for a directly-named leaf. Still open,
  explicitly scoped out rather than accidental: a nested pattern's own leaves stay unresolved (no
  AST node represents an intermediate destructured slot's value to extract further from); a rest
  element is never given a value (no static model for "everything except these properties"); array
  elements have no mutation tracking at all (matching object properties before round 60 would be a
  much larger, unrequested surface — `push`/`splice`/index-assignment/`length`).
- Round 62 closed, in one round, every remaining binding-creation site and every still-fixable
  ceiling from the lists above: destructured/method/accessor/constructor parameters, catch-clause
  variables, function/class/enum/namespace names (all now shadow correctly); nested destructuring
  and per-element defaults (applied only when provably absent); object spread; numeric index
  reads and direct index mutation (`arr[0] = x`); compound mutations on a member; `enum`,
  `namespace`, and class-`static` members. The round-46 "only bare `${NAME}` template holes fold"
  line was already obsolete (any expression in a hole folds since round 58) and is superseded.
  Still open, each deliberate: a rest element's value; a nested pattern's *intermediate*-level
  default (`{ a: { b } = {...} }`); array mutation beyond a direct index write (`push`/`splice`/
  `length`); computed keys; instance/prototype class members; `export * as ns`; the legacy
  `export =` form; and the Python resolver's conditional-branch module-constant gap — a
  single-value (`str | None`) model across every Python gate, so modeling a conditional value set
  there is a separate refactor of a separate subsystem that no review round has raised.
- Round 63 replaced the round 58–62 per-property member model with one path model
  (`replayPath`/`exprValues`/`literalValues`; no per-property structure exists any more), closing
  the reviewer's nested-destructuring case and the whole sibling class (chained reads, nested
  member writes, spread from a mutated base, class statics replaced then read through, property
  compound self-reference), plus the previously listed ceilings that fell out of the same model:
  intermediate-level destructuring defaults, rest elements (object minus siblings, array shifted),
  computed keys that fold to a constant (ambiguous → conditional match, unknown → possible
  overwrite), and ternary/short-circuit expression values (both branches reachable). Still open,
  each deliberate: *reverse* aliasing — a mutation made through one binding is visible through
  every path that *reaches* that object (a literal member, a spread's nested object, a destructured
  object), but not the other way round (`const { llm } = config; llm.provider = "x";` is not
  reflected in a later `config.llm.provider` read — a points-to analysis, a different class of
  tool); `delete obj.key`, `Object.assign`, `push`/`splice`/`length` and other call-based
  mutations (call semantics); `this.x` instance/prototype members; a pattern nested inside a rest
  element (`...[a, b]`); `export * as ns`; the legacy `export =` form; and the Python resolver's
  conditional-branch module-constant gap.
