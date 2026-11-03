# Execution Plan: ANY-733 CI validator text scanning

## Status

- State: active
- Owner: agent
- Created: 2026-11-03
- Last updated: 2026-11-03
- Review date: 2026-11-03
- Next action: user review; rerun quick-check in an environment with passwordless sudo
- Blocker: full green baseline requires passwordless sudo for the existing activation-marker test

## Goal

Remove quadratic processing of fence lines and JS/TS import candidates in CI validators.

## Scope

Only metadata and architecture validators, focused regressions, and validation evidence.
Runtime products, logging, new dependencies and a full JS/Markdown parser are out of scope.

## Relevant docs

- `docs/architecture/package-layering.md`
- `docs/agent/coding-conventions.md`

## Contracts touched

No API, DB, configuration, event or frontend changes. Preserve supported import forms and
metadata diagnostics. Treat a bare CR as a line ending, consistent with splitlines.
The import recognizer remains textual, including matches inside comments and strings.

## Implementation steps

- [x] Normalize fence line endings and prevent marker backtracking.
- [x] Scan quote-free import spans once, preserving the existing textual contract.
- [x] Add syntax, boundary and adversarial regressions; compare scaling at multiple sizes.
- [x] Run targeted tests, architecture, quick-check and documentation checks; review diff.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-03 | Use Python span scanning instead of the TS scope resolver | Preserve the textual contract without adding Node subprocess coupling. |
| 2026-11-03 | Split named google imports at closing braces | Preserve that rule's separate contract without repeated scans of overlapping brace contents. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-03 | Read callers and existing tests; system doctor lacks pytest/pydantic; managed Python 3.12 environment exists. | Implement and validate in managed environment. |

## Open questions

None.

## Follow-up debt

None planned.

## Validation evidence

- Managed Python 3.12 doctor passed. The initial system-Python doctor lacked pytest/pydantic.
- Focused metadata/import/scaling suite: 61 tests passed.
- Architecture validation, documentation validation, generated-doc drift check passed.
- Ruff passed for both validators and focused tests. The baseline quick-check script has three
  pre-existing lint findings outside the changed target list; left unchanged.
- Differential comparison against HEAD's recognizer: identical results for 10,000 seeded random
  text cases and all 287 JS/TS source files under apps/packages/scripts.
- Local benchmark through real validator entry points, median of three runs (seconds):

| Input size | Fence before | Fence after | Imports before | Imports after |
|---:|---:|---:|---:|---:|
| 1,000 | 0.013467 | 0.000007 | 0.049904 | 0.000057 |
| 2,000 | 0.051575 | 0.000006 | 0.142760 | 0.000046 |
| 4,000 | 0.206835 | 0.000006 | 0.657516 | 0.000142 |
| 8,000 | 0.878396 | 0.000007 | 3.941449 | 0.000138 |

These are local observations, not absolute CI limits. Regression tests compare median growth
for eightfold input growth against a generous relative bound below quadratic growth.
The new regression modules are included in the canonical quick-check target list.

### Complexity and compatibility review

Fence marker runs are possessive, so the marker cannot be repeatedly repartitioned into rest.
Only terminal LF/CR is removed before matching; indentation and info strings are retained.
Bare CR now terminates a fence line consistently with splitlines; tests explicitly cover it.

The import scan splits at quotes in O(n) and examines each span at most a constant number of
times. The first keyword suffices for a from-clause match because all intervening text is
quote-free; side-effect imports separately require a keyword/whitespace suffix, preserving a
valid import after malformed candidates. Accepted module matches consume both quotes, as before.
Suffix regexes contain no overlapping arbitrary-text/whitespace repetitions. Named google imports
use disjoint brace spans, preserving the old rule even for quoted names. Time and auxiliary memory
are O(n); no statement-length limit or new syntax restriction is introduced.

Self-review checked real callers, supported forms, negative cases, malformed-prefix recovery,
ATAI006/ATAI007 diagnostics, line endings and duplicate metadata sections. No external writes.

### Final baseline outcome

Canonical quick-check completed: **3059 passed, 12 skipped, 486 deselected, 1 failed**.
The sole failure is the unchanged
`tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`:
`sudo -n -u nobody` reports "interactive authentication is required".
The task does not alter runner.py, the activation-marker implementation or that test.
This is an environment limitation; no test was suppressed or changed to obtain a green result.
All focused regressions ran successfully within the baseline as well as separately.

The initial sandbox PyPI DNS failure was resolved by the approved canonical-check retry.
No runtime, Docker, frontend E2E, live-provider or PostgreSQL-specific checks were added for this
CI-only change. Acceptance still requires reviewing the diff and a green baseline in a suitable
CI environment. Pre-existing local-skill-name references in unrelated execution plans were left
untouched after the repository-wide convention check.
