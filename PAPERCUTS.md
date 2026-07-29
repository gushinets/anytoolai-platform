# Agent Papercuts

This tracked log captures minor repository and tooling friction encountered by agents. Search for the
same underlying problem before adding an entry, append entries oldest-to-newest, and keep sensitive
information out of the log. Product bugs, blockers, and tracked issues belong in their established
workflows.

Use the agent environment's local time. Use the exact model or agent identity when available;
otherwise use `unknown`.

```text
## YYYY-MM-DD HH:MM - <model or agent, or unknown> - <operating system>

<What you were doing> в†’ <what got in the way>. Include a likely cause, workaround, or suggested fix
when known.
```

## 2026-07-16 13:02 - Codex (GPT-5) - Windows

Running the canonical `quick-check` в†’ the isolated environment removed editable packages, then could
not restore build requirements because sandbox networking blocked PyPI. Rerunning with approved
network access restored the dependencies and passed all checks.
## 2026-07-17 15:15 - Codex (GPT-5) - Windows

Running focused `uv run pytest` suites for workflow recovery review -> `uv` first tried to use a
blocked global cache path, and `pytest` then failed to enumerate a reused `.tmp\\pytest-of-jackd`
base temp directory with `PermissionError`. Using repo-local `UV_CACHE_DIR` plus a fresh
`--basetemp` let the suites pass; the harness could set those defaults automatically for agent runs.

## 2026-07-22 12:33 - GPT-5 Codex - Windows

Parallel PowerShell file reads through `multi_tool_use.parallel` в†’ most `shell_command` calls failed
with `windows sandbox: CreateProcessWithLogonW failed: 1056`. Retrying the reads as smaller
 individual/limited parallel batches worked; likely transient Windows sandbox process/session state.

## 2026-07-22 13:05 - Codex (GPT-5) - Windows

Using `rg` to inspect the checked-out PR during review в†’ `rg.exe` failed with Access Denied under
the Windows sandbox. PowerShell file reads still worked; investigate the sandbox executable policy or
provide a repository-approved search fallback.

## 2026-07-22 13:45 - Codex (GPT-5) - Windows

Running `python scripts/agent/runner.py generate-docs --check` directly -> the system Python lacked
`yaml`, and `uv run` could also hit the known global cache permission problem under the sandbox.
Use the project-managed environment (for example `.quick-check-venv\\Scripts\\python.exe` or a
repo-local `uv` cache) for generated-doc checks, or make the runner self-select the same
dependency-managed interpreter as the canonical checks.

## 2026-07-23 16:46 - Codex (GPT-5) - Windows

Running the canonical `quick-check` during PR review timed out at the shell boundary but left its
Python child processes running. Process command-line inspection with `Get-CimInstance Win32_Process`
was also denied by the sandbox; matching start times and explicit process IDs allowed safe cleanup.
The runner or shell wrapper should terminate the full child-process tree on timeout. The bundled
GitHub review-thread helper also failed because `gh` was not available on `PATH`; the connected
GitHub app's thread-listing tool provided the needed read-only fallback.

## 2026-07-23 17:23 - Codex (GPT-5) - Windows

Running the required `python scripts/agent/runner.py doctor` before a focused backend change в†’
doctor used the system Python and failed because pytest, YAML, and Pydantic were absent, although
the repository's managed `uv` environment was available. Doctor could bootstrap or inspect the
managed environment before treating system-interpreter packages as required.

## 2026-07-29 19:07 - Codex (GPT-5) - Windows

Restoring one checkout block in a workflow with several identical checkout steps -> a broad
`apply_patch` context matched the first job instead of the intended PostgreSQL job. Including the
unique job name in the patch context and verifying against the parent revision caught the mismatch
before commit.

## 2026-07-29 19:32 - Codex (GPT-5) - Windows

Validating `uv run alembic -c ..\\..\\migrations\\platform\\alembic.ini upgrade head --sql` from
`apps\\platform-api` -> `uv` tried to rebuild transitive dependency `litellm` and failed because
`link.exe` was unavailable for the Rust-backed wheel build. Running the same Alembic CLI through the
repo-root `.venv\\Scripts\\python.exe -m alembic` succeeded, so a documented repo-level Alembic
entrypoint or a lighter nested-project dependency path would avoid this unrelated toolchain trap.
