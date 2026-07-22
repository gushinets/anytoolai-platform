# Agent Papercuts

This tracked log captures minor repository and tooling friction encountered by agents. Search for the
same underlying problem before adding an entry, append entries oldest-to-newest, and keep sensitive
information out of the log. Product bugs, blockers, and tracked issues belong in their established
workflows.

Use the agent environment's local time. Use the exact model or agent identity when available;
otherwise use `unknown`.

```text
## YYYY-MM-DD HH:MM - <model or agent, or unknown> - <operating system>

<What you were doing> → <what got in the way>. Include a likely cause, workaround, or suggested fix
when known.
```

## 2026-07-16 13:02 - Codex (GPT-5) - Windows

Running the canonical `quick-check` → the isolated environment removed editable packages, then could
not restore build requirements because sandbox networking blocked PyPI. Rerunning with approved
network access restored the dependencies and passed all checks.
## 2026-07-17 15:15 - Codex (GPT-5) - Windows

Running focused `uv run pytest` suites for workflow recovery review -> `uv` first tried to use a
blocked global cache path, and `pytest` then failed to enumerate a reused `.tmp\\pytest-of-jackd`
base temp directory with `PermissionError`. Using repo-local `UV_CACHE_DIR` plus a fresh
`--basetemp` let the suites pass; the harness could set those defaults automatically for agent runs.

## 2026-07-20 23:22 - Codex (GPT-5) - Windows

Running `python scripts/agent/runner.py generate-docs --check` during an A13 review -> the system
Python path could import the repo package but lacked `yaml`, causing `ModuleNotFoundError`.
Use the project environment/`uv run` for generated-doc checks or make the runner self-select the
same dependency-managed interpreter as the canonical checks.
## 2026-07-22 12:33 - GPT-5 Codex - Windows

Parallel PowerShell file reads through `multi_tool_use.parallel` → most `shell_command` calls failed
with `windows sandbox: CreateProcessWithLogonW failed: 1056`. Retrying the reads as smaller
individual/limited parallel batches worked; likely transient Windows sandbox process/session state.
