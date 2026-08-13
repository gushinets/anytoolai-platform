# Extension Boundary Generated-Tree Exclusions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Status

- State: active
- Owner: agent
- Created: 2026-08-13
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: add a failing architecture regression proving extension scans ignore dependency and
  build-output directories.
- Blocker: none

**Goal:** Keep extension prompt/provider boundary tests focused on tracked extension source instead
of recursively scanning installed dependencies and generated build output.

**Architecture:** Extract the extension-source iterator used by the boundary test and prune known
generated directory segments before reading file contents. Before pruning, enforce a repository
invariant that no tracked extension source may live under those generated directory names, so a
future tracked file fails explicitly instead of disappearing from the content scan.

**Tech stack:** Python 3.12, pathlib, pytest.

## Global Constraints

- Do not weaken checks for tracked `.ts`, `.tsx`, `.md`, or `.json` extension source files.
- Treat `node_modules`, `dist`, and `.wxt` as generated-only directory names under `extensions/` and
  mechanically reject any tracked file placed below them before excluding those trees from the
  content scan.
- Keep architecture validation deterministic before and after frontend dependency installation.

---

### Task 1: Prune generated extension trees

**Files:**

- Modify: `tests/architecture/test_no_prompts_inside_extensions.py`

**Interfaces:**

- Produces: `iter_extension_source_files(root: Path) -> Iterator[Path]` for the existing boundary
  assertion and its regression test.

- [ ] **Step 1: Add a failing generated-tree regression**

  Build a temporary extension tree containing `src/background.ts` and
  `node_modules/example/test.ts`. Assert the iterator returns the tracked source file and excludes
  the dependency file. Add a separate invariant regression which supplies a tracked path such as
  `extensions/demo/dist/hidden.ts` and asserts that it is reported as a violation:

  ```python
  assert list(iter_extension_source_files(root)) == [root / "src" / "background.ts"]
  assert generated_directory_violations(
      [Path("extensions/demo/dist/hidden.ts")]
  ) == [Path("extensions/demo/dist/hidden.ts")]
  ```

- [ ] **Step 2: Run the focused architecture test and confirm failure**

  Run:

  ```text
  uv run --locked python -m pytest tests/architecture/test_no_prompts_inside_extensions.py -q
  ```

  Expected: FAIL because the current recursive glob includes `node_modules`.

- [ ] **Step 3: Enforce the tracked-source invariant, then exclude generated segments**

  Add `generated_directory_violations(paths: Iterable[Path]) -> list[Path]`. Feed it the sorted
  result of `git ls-files -- extensions` and fail the architecture test if any tracked path has a
  parent segment in `{"node_modules", "dist", ".wxt"}`. Only after that invariant passes, make the
  iterator prune those generated directory segments. Retain the current suffix and README/AGENTS
  exclusions in one place.

- [ ] **Step 4: Verify before and after a frozen frontend install**

  Run:

  ```text
  python scripts/agent/runner.py quick-check
  pnpm install --frozen-lockfile
  python scripts/agent/runner.py quick-check
  git diff --check
  ```

  Expected: both quick-check runs pass; generated dependencies do not affect the source boundary.

## Validation

- [ ] focused red/green architecture regression
- [ ] quick-check without frontend dependencies
- [ ] quick-check after frozen frontend dependency installation
- [ ] `git diff --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-13 | Prune generated directory segments instead of weakening forbidden tokens. | The reported `system prompt` text came from CE-kit test fixtures linked into an extension's `node_modules`, not extension-owned source. |
| 2026-08-13 | Reject tracked files under generated-only directory names before pruning them. | Directory-name pruning alone could hide tracked source; the invariant makes that repository state an explicit architecture failure. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-13 | Reproduced quick-check changing from 510 passing tests to one architecture failure after `pnpm install --frozen-lockfile` populated extension dependency links. | Add the isolated iterator regression. |

## Open questions

None.

## Follow-up debt

None identified.
