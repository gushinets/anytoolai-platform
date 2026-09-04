# Execution Plan: ANY-341 Add a Real Frontend Lint Gate Separate From TypeScript Typecheck

## Status

- State: active
- Owner: agent
- Created: 2026-09-04 (backfilled — implementation and three code-review rounds had already
  landed before this file existed; see `docs/exec-plans/active/any-338-propagate-core-closed-enums.md`'s
  own round-3 finding for the precedent).
- Last updated: 2026-09-04
- Review date: 2026-09-04
- Next action: none — implementation and code-review rounds 1-3 addressed; move to `completed/`
  once merged.
- Blocker: none

## Goal

Every frontend workspace's `lint` script was literally `tsc --noEmit` (identical to, or for
`kernel-demo-ce` prefixed onto, its own `typecheck` script), so `lint` and `typecheck` caught the
same class of problems and no real correctness-oriented linter existed anywhere in the repo. Add
ESLint + `typescript-eslint` (type-checked) as a real, distinct lint gate across every maintained
frontend pnpm workspace, wired into the canonical `frontend_check()`/`full-check` command, without
introducing a formatter, broad stylistic enforcement, or a second competing linter.

## Scope

### In scope

- Pick one monorepo-wide linter (ESLint 10 + `typescript-eslint`'s `recommendedTypeChecked`) and
  configure it for correctness/unsafe-construct rules only — not the `stylistic` rule family.
- One shared `eslint.config.base.mjs` at the repo root, one thin per-workspace `eslint.config.mjs`
  in each of the 7 pnpm workspaces (`apps/web-mirror`, `extensions/kernel-demo-ce`,
  `packages/frontend/{ce-kit,shared-ui,web-result-kit}`,
  `tests/e2e/{client-handoff-smoke,stakeholder-demo-browser}`), including the two workspaces that
  had no `lint` script (or no TypeScript at all) before this ticket.
- Replace every `"lint": "tsc --noEmit"` alias with a real `"lint": "eslint . --max-warnings=0"`;
  `typecheck` scripts stay untouched.
- Explicit, minimal ignores for generated/build output: the committed generated
  `platformApi.ts`, `.next/`, `.wxt/`, `.output/`, `dist/`, `build/`, `*.tsbuildinfo`.
- Insert `["pnpm", "-r", "lint"]` into `frontend_check()`'s `run_sequence` in
  `scripts/agent/runner.py`, ahead of `typecheck` — no `--if-present`, a missing `lint` script
  fails loudly.
- Fix only the baseline findings needed to turn the new gate green (see Decision log for how the
  volume was kept proportionate).

### Out of scope

- Mass stylistic rewriting; adding a formatter or enforcing formatting through lint (no Prettier,
  no Biome).
- Fixing closed HTTP contract strings (ANY-338's scope).
- A runtime-schema validation library; new browser automation; `mypy` or backend lint changes; TS
  project references / build-mode restructuring.

## Relevant docs

- `plans/ANY-341.md` (issue + implementation plan + all three code-review rounds, gitignored —
  local-only, not part of the git history).
- `docs/agent/coding-conventions.md`'s "Lint vs typecheck" section (already stated the target
  state this ticket implements: "Do not add a new `lint` script that only aliases
  `tsc --noEmit`").

## Contracts touched

- None. This is tooling-only: no wire contracts, OpenAPI shapes, or generated CE-kit types change.
  `generate-api-types:check` stayed green throughout (verified after every round).

## Implementation steps

- [x] `eslint.config.base.mjs`: shared `baseConfig({ tsconfigRootDir, react, ignores })` —
      `@eslint/js` recommended (all files) + `typescript-eslint`'s `recommendedTypeChecked`
      (scoped to `**/*.{ts,mts,cts,tsx}` via `tseslint.config()`'s `extends` key — spreading it
      unscoped makes ESLint try to type-check every file in the workspace, including its own
      `eslint.config.mjs`), a Node-globals block for `.js`/`.mjs`/`.cjs` build/config scripts, and
      `eslint-plugin-react-hooks`'s two correctness rules (`rules-of-hooks`, `exhaustive-deps`,
      pinned `^5.2.0` — `6.x`+ is a compiler-adjacent rewrite requiring `@babel/core`) for
      workspaces with JSX.
- [x] Per-workspace `eslint.config.mjs` in all 7 workspaces, each a few lines calling
      `baseConfig()` with its own `tsconfigRootDir`/`react`/`ignores`; the one workspace with zero
      TypeScript (`tests/e2e/stakeholder-demo-browser`) gets its own minimal `@eslint/js` +
      `globals.node` config instead, since `baseConfig()`'s type-checked setup doesn't apply.
- [x] `lint` scripts: replaced 5 `tsc --noEmit` aliases, added 2 from scratch (including a
      JS-only one).
- [x] `scripts/agent/runner.py`: `["pnpm", "-r", "lint"]` inserted into `frontend_check()`.
- [x] Baseline fix pass: 296 raw findings surfaced on first run (concentrated in `ce-kit`, ~144
      `.ts`/`.tsx` files repo-wide). Turned off two rules that fire on syntax, not unsafe values
      (`require-await`, `no-unnecessary-type-assertion` — 269 of the 296 findings), scoped to test
      files/helpers only after round-1 review found the initial cut too broad; fixed the ~35
      remaining genuine findings (unsafe `any` flow, a `Request` stringification bug, unhandled
      promises in `onClick` handlers, an `ImportMetaEnv` cast, a real exception-semantics
      regression a mechanical `async`-removal fix introduced, one `expect.any()` false positive)
      at their source. Full findings/fixes/skip-reasoning breakdown is in `plans/ANY-341.md`'s
      three review-round sections.
- [x] `next.config.ts`: `eslint: { ignoreDuringBuilds: true }` — the canonical gate already lints
      before its own build step, so `next build`'s internal lint pass would otherwise be
      redundant; comment corrected in round 3 to not overclaim this for every `next build`
      invocation (`client_handoff_smoke()` builds web-mirror directly, outside the canonical
      gate — still covered by `full-check`'s separate required check on the same PR).
- [x] `tests/test_runner.py`: updated the one test pinned to `frontend_check()`'s exact command
      sequence, and added a new regression test proving a `pnpm -r lint` failure actually stops
      the sequence and propagates, not just that the commands run in order.

## Validation

- [x] `pnpm -r lint` — run repeatedly across all three review rounds and re-verified 3x
      consecutively in round 3 to rule out flakiness; green on all 7 workspaces each time.
- [x] `python scripts/agent/runner.py frontend-check` — green.
- [x] `python scripts/agent/runner.py full-check` — green every round (1169 → 1177 backend tests
      over the session, the latter increase from unrelated concurrent activity in this shared
      working tree, not this PR's diff; `ce-kit` vitest 281 → 288 for the same reason).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-04 | ESLint 10 (not the researched ESLint 9) + `typescript-eslint@^8.69.0`. | `eslint@9.x` installs as deprecated/EOL right now; `typescript-eslint`/`@eslint/js` both declare `eslint ^10.0.0` support. |
| 2026-09-04 | `eslint-plugin-react-hooks` pinned to `^5.2.0`, not latest `7.x`. | `6.x`+ is a rewrite requiring `@babel/core` with a much larger, compiler-adjacent rule set; `5.2.0` is the last version with just the two correctness rules and no extra runtime deps. |
| 2026-09-04 | `require-await`/`no-unnecessary-type-assertion` turned off for test files/helpers (`**/*.test.ts(x)`, `**/test/**`, `**/tests/**`), not the whole monorepo. | Round-1 review: an unscoped, monorepo-wide disable (the initial cut) would also mask a real defect in production code. Neither rule catches an unsafe/untyped value; disabling them only where this codebase's `vi.fn()`-based test doubles use the pattern deliberately keeps the "correctness and unsafe constructs" gate intact for `src/`. The ~9 production-code sites this uncovered were fixed at their source instead of suppressed. |
| 2026-09-04 | `chrome.tabs.sendMessage`'s response typed via explicit generics at the call site, not a post-hoc `as` cast. | The default-`any` response generic meant `no-unnecessary-type-assertion` couldn't distinguish "asserting a type onto `any`" from a genuinely redundant assertion — deleting the assertion (as the rule suggested) would have silently left the value `any`. Verified the fix produces a real (non-`any`) type with a throwaway `const x: never = ...` probe before and after. |
| 2026-09-04 | Reverted `localStorageAdapter.ts`/`inMemoryAsyncStorage.ts` from a mechanical `async` → plain-function-+`Promise.resolve()` rewrite back to real `async` methods, with a scoped `require-await` override instead. | Round-2 review: the mechanical rewrite changed real behavior — a synchronous `localStorage.setItem`/`removeItem` throw (QuotaExceededError, private-browsing SecurityError) used to become a rejected Promise via the implicit `async` wrapper; as a plain function it now throws synchronously instead, before any Promise exists. `async` here is load-bearing (throw → rejection conversion), not test-mock convenience. |
| 2026-09-04 | Did not add `typescript: { ignoreBuildErrors: true }` alongside `eslint: { ignoreDuringBuilds: true }` in `next.config.ts`. | Investigated in round 2: web-mirror's tsconfig includes `.next/types/**/*.ts` (Next's generated typed-routes output), which doesn't exist on a from-scratch checkout until `next build` runs once — `pnpm -r typecheck`'s plain `tsc --noEmit` can't validate typed-routes usage the way `next build`'s own (later, self-generating) typecheck pass can. Disabling it would trade a real redundant-work cost for a real first-build coverage gap. |
| 2026-09-04 | Did not create a `docs/exec-plans/active/` file during initial implementation; backfilled this one afterward, once the PR needed to link one. | Same precedent as ANY-338's own round-3 finding: `CLAUDE.md`'s "before coding" exec-plan requirement wasn't followed for this ticket either. `plans/ANY-341.md` (gitignored) already carried the full plan and three review rounds' worth of findings/fixes by the time this was noticed, so this file distills that record into the tracked location the PR template and `CLAUDE.md` both expect, rather than redoing the work. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-04 | Implemented: shared + 7 per-workspace ESLint configs, `lint` script replacements, `frontend_check()` wiring, baseline fix pass (296 → 0 findings). `frontend-check`/`full-check` green. Committed. | Await code review. |
| 2026-09-04 | Code review round 1 found the global `require-await`/`no-unnecessary-type-assertion` disable was too broad, a test asserting only command order (not real lint-failure propagation), and a silent-fallback regression in a test fake. Fixed all three; 6 lower-priority findings deliberately skipped with recorded reasoning (see `plans/ANY-341.md`). Re-verified `pnpm -r lint`/`frontend-check`/`full-check` green. | Await round-2 review. |
| 2026-09-04 | Code review round 2 found the round-1 `async`-removal fix in `localStorageAdapter.ts`/`inMemoryAsyncStorage.ts` was a real exception-semantics regression; reverted with a properly-scoped, documented rule override instead. Investigated (and declined) matching `typescript.ignoreBuildErrors` to `eslint.ignoreDuringBuilds` in `next.config.ts` — real first-build coverage gap, not worth it. Re-verified green. | Await round-3 review. |
| 2026-09-04 | Code review round 3 found the `next.config.ts` lint-ordering comment overclaimed a guarantee that doesn't hold for `client_handoff_smoke()`'s direct build path (verified true, but confirmed the separate required `full-check` check still closes the gap) and flagged an untracked, pre-existing `CLAUDE.md` as stale (unrelated to this PR, left alone). Corrected the comment. Re-verifying also surfaced one new, review-unrelated `expect.any()` false positive from unrelated concurrent activity in this shared working tree; fixed with a single inline suppression. Re-verified `pnpm -r lint` (3x), `frontend-check`, `full-check` green. Backfilled this exec plan. | Move to `completed/` once merged. |

## Open questions

- None.

## Follow-up debt

- None identified beyond the documented, deliberate rule scoping above.
