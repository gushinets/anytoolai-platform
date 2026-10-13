# Apply selected Kernel Demo prompts

## Status

- State: active
- Owner: agent
- Created: 2026-10-13
- Last updated: 2026-10-13
- Review date: 2026-10-13
- Next action: finish isolated checks and publish the scoped change
- Blocker: none

## Goal

Make the selected Atom Lab prompt variants the working Kernel Demo templates, preserve a short
decision report, and publish only this change as a commit, Linear issue, and pull request.

## Scope

- Copy the ten changed templates exactly from the tested snapshots: A07 D1, A09 C, other atoms B1.
- Keep A06 unchanged, retain existing prompt references and schemas, and update the docs index.
- Preserve local experiment archives and all pre-existing SDK/runtime/lockfile changes outside the commit.
- No new paid generation, model routing changes, product prompt updates, or deployment.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/architecture/config-model.md`
- `docs/agent/prompting-guidelines.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- Config: Kernel Demo Markdown prompt contents only; references and schemas unchanged.
- API, DB, events, frontend: unchanged.

## Implementation steps

- [x] Run doctor and verify tested snapshot hashes and current Git scope.
- [x] Apply exact prompt texts, add a concise results report, and update `docs/index.md`.
- [x] Validate configuration loading, documentation, and credential-free backend checks on the isolated change.
- [ ] Commit only the approved files, create a classified Linear issue, and publish the linked PR.

## Validation

- Snapshot SHA256 and unchanged A06/source-file checks.
- `python scripts/agent/runner.py doctor`
- `python scripts/agent/runner.py validate-configs`
- `python scripts/agent/runner.py validate-docs`
- `python scripts/agent/runner.py generate-docs --check`
- `python scripts/agent/runner.py quick-check`
- Credential-free Kernel Demo smoke checks appropriate to this prompt-only change.

## Progress

- 2026-10-13: Doctor passed. Working checkout is main at b04f6a9; SDK/runtime changes and local
  experiment archives already exist. They must remain outside this commit. Only the prompt package
  selected by the completed experiments is authorized for adoption.
- 2026-10-13: Updated origin/main and created `codex/apply-kernel-demo-prompts` from 0c81cc65.
  Exact snapshot hashes matched; ten working templates were copied, A06 retained. A separate clean
  managed checkout contains only these ten files, the short report, docs index, and this plan.
  Initial validation caught missing plan metadata; corrected before continuing. Generated-doc
  validation is run with the managed environment's Python because system Python lacks markdown-it.
- 2026-10-13: Isolated ConfigLoader verified all eleven references and selected content SHA256,
  including unchanged A06. Canonical quick-check passed: 2185 passed, 7 skipped, 485 deselected
  by the existing `not slow` filter. Config, architecture, docs and generated-doc checks passed.
  Only thirteen authorized files are staged; SDK/Gateway/dependency changes and archives excluded.
  No new paid calls or Compose/deployment actions were performed. Commit and external publication follow.

## Open questions

None.
