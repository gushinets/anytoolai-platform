# Generated-Doc Locked-Environment Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Status

- State: active
- Owner: agent
- Created: 2026-08-13
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: add a failing runner regression that reproduces standalone generated-doc execution
  outside the repository's locked Python environment.
- Blocker: none

**Goal:** Make `python scripts/agent/runner.py generate-docs [--check]` render with repository-locked
dependencies even when the caller's system Python has a different FastAPI version.

**Architecture:** Keep the public runner command unchanged. Verify the resolved interpreter path
before bypassing bootstrap: accept the quick-check interpreter, or the locked project interpreter
for a generated-doc child carrying its dedicated recursion guard. Every other caller re-executes
once through `uv run --locked`; a guard under the wrong interpreter fails explicitly instead of
silently rendering with caller dependencies.

**Tech stack:** Python 3.12, `uv`, FastAPI OpenAPI generation, pytest.

## Global Constraints

- Do not hand-edit generated documentation or `uv.lock`.
- Preserve `python scripts/agent/runner.py generate-docs [--check]` as the public cross-platform
  command.
- Keep caller-provided `PYTHONPATH` out of the locked subprocess.
- Avoid recursion with one generated-doc bootstrap flag plus resolved managed-interpreter checks;
  an environment flag alone is never proof of the active interpreter.

---

### Task 1: Lock standalone generated-doc execution

**Files:**

- Modify: `scripts/agent/runner.py`
- Test: `tests/test_runner.py`
- Verify: `tests/test_docs_generation.py`

**Interfaces:**

- Consumes: `uv_command()`, `baseline_env()`, `run_with_env()`, `quick_check_python()`, and
  `ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED` from the existing runner/quick-check flow.
- Produces: one private bootstrap decision used only by `generate_docs(check: bool = False)` and an
  `ANYTOOLAI_GENERATE_DOCS_BOOTSTRAPPED=1` recursion guard for the locked child process.

- [ ] **Step 1: Write failing runner tests for outer and inner execution**

  Add focused tests to `tests/test_runner.py` which monkeypatch `run_with_env`, `uv_command`, and
  the two bootstrap flags. Assert that an outer `generate_docs(check=True)` call runs exactly:

  ```python
  [
      "/usr/local/bin/uv",
      "run",
      "--locked",
      "python",
      str(Path(runner.__file__).resolve()),
      "generate-docs",
      "--check",
  ]
  ```

  Assert the child environment contains `ANYTOOLAI_GENERATE_DOCS_BOOTSTRAPPED=1` and excludes
  `PYTHONPATH`. Add tests proving that the resolved quick-check interpreter bypasses re-exec, while
  a manually set `ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED=1` under system Python does not. Also cover a
  generated-doc guard under the wrong interpreter and require an explicit failure rather than
  recursion or rendering.

- [ ] **Step 2: Run the focused tests and confirm the bootstrap assertion fails**

  Run:

  ```text
  uv run --locked python -m pytest tests/test_runner.py -k generate_docs -q
  ```

  Expected: the new outer-execution test fails because `generate_docs()` currently renders in the
  caller's interpreter instead of invoking locked `uv`.

- [ ] **Step 3: Add the single locked re-exec boundary**

  In `scripts/agent/runner.py`, add resolved-path helpers for the quick-check interpreter and locked
  project interpreter. `generate_docs()` may enter the existing write/check path only when the
  current interpreter is the quick-check interpreter, or when both the generated-doc guard and the
  locked project interpreter match. If a generated-doc guard is present under any other
  interpreter, fail with a safe diagnostic. Otherwise build a clean `baseline_env()`, set
  `ANYTOOLAI_GENERATE_DOCS_BOOTSTRAPPED=1`, and return `run_with_env()` for the exact command asserted
  above. Do not use `ANYTOOLAI_QUICK_CHECK_BOOTSTRAPPED` as environment proof.

- [ ] **Step 4: Run focused runner and docs-generation tests**

  Run:

  ```text
  uv run --locked python -m pytest tests/test_runner.py tests/test_docs_generation.py -q
  ```

  Expected: all selected tests pass.

- [ ] **Step 5: Reproduce the original mismatched-interpreter case**

  From a shell whose system Python does not match the lock, record the versions and run:

  ```text
  python -c "import fastapi; print(fastapi.__version__)"
  python scripts/agent/runner.py generate-docs --check
  ```

  Expected: the public command reports `Generated documentation is current` because rendering
  occurs in the locked child environment, regardless of the printed system FastAPI version.

- [ ] **Step 6: Run repository validation**

  Run:

  ```text
  python scripts/agent/runner.py doctor
  python scripts/agent/runner.py validate-docs
  python scripts/agent/runner.py quick-check
  git diff --check
  ```

  Expected: every command exits zero.

## Validation

- [ ] focused red/green runner bootstrap regression
- [ ] `python scripts/agent/runner.py generate-docs --check` from a mismatched system interpreter
- [ ] `python scripts/agent/runner.py validate-docs`
- [ ] `python scripts/agent/runner.py quick-check`
- [ ] `git diff --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-13 | Re-execute standalone generation through locked `uv` instead of accepting system dependency drift. | The same tree passed in the locked quick-check environment with FastAPI 0.137.0 but produced stale `openapi.json` under system FastAPI 0.115.6. Generated output must be a function of the repository lock, not caller state. |
| 2026-08-13 | Keep the fix out of the weekly documentation-only change. | The discovered issue changes runner behavior and needs its own regression and review boundary. |
| 2026-08-13 | Require resolved managed-interpreter identity in addition to bootstrap flags. | Callers can set environment variables manually; the quick-check bootstrap contract itself treats a flag under the wrong interpreter as an error. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-13 | Reproduced false OpenAPI drift under system FastAPI 0.115.6 and confirmed the same check passes under the locked managed FastAPI 0.137.0 environment. | Add the failing runner regression before changing bootstrap behavior. |

## Open questions

None.

## Follow-up debt

None identified.
