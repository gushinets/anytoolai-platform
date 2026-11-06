# ANY-818: eight independent review fixes

## Status

- State: active
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: parent review, commit and push, then fresh independent Astra review and CI.
- Blocker: none.

Scope: address [PR #259](https://github.com/gushinets/anytoolai-platform/pull/259)
Astra review findings 1–8 without changing product runtime,
working acceptance data, or the unrelated experiment files.

Follow-up scope: prevent framing of the Atom Lab HTML shell, remove the independent
saved-prompt character ceiling in favor of configured UTF-8 bytes, preserve known
successful trial evidence through unchanged preset saves and retired-model history
restores, clarify the local-only no-code launch contract, and share the identical
atom-not-found OpenAPI response across its three operations. Existing trust checks,
new-run model admission, production ingress and the 404 error envelope remain intact.

Follow-up validation: focused API and Chromium regressions, canonical OpenAPI/client
generation, docs generation checks, and frontend-check. Use only isolated test fixtures
and mocked browser transport; no working DB, migrations, deployment or paid calls.

## Plan

1. Reproduce and fix local no-code Host/Origin authorization, saved prompt UTF-8
   limit, and prompt-route 404 documentation with API regression tests.
2. Fix prompt-source loading/reset, restored successful trial provenance, explicit
   preset provenance restoration, background error navigation, and preset prompt
   labels with focused browser regressions.
3. Regenerate canonical OpenAPI/client artifacts and run focused plus repository
   checks. Leave changes uncommitted for parent review and PR update.

## Validation and risks

- Doctor passed before edits (2026-11-06).
- API storage tests use isolated test fixtures; browser tests use mocked transport.
- No paid provider calls, deployment, migration, or working acceptance DB access.
- Regression reproduction, implementation, generated artifacts and local checks are complete.
  Commit, push, independent review and required CI are owned by the parent agent.

## Repairs

All eight findings were reproduced before production edits:

1. No-code access now checks loopback Host and same Origin on every protected route;
   code-protected remote access is unchanged. Local origin-free CLI reads still work.
2. Saved prompts load the same environment-backed settings as run admission and reject
   oversized UTF-8 text with the existing `422 prompt_invalid` field envelope.
3. Reset is disabled and its handler guarded until a historical prompt source resolves.
   Failed loads preserve that guard; missing sources detach before platform reset is allowed.
4. Restoring a compatible successful history snapshot initializes trial evidence from that
   exact snapshot. Existing text/source/model/reasoning/input comparisons invalidate it.
5. Explicit preset reopen compares `source_run_id` too, confirms discard, and restores the
   immutable version's provenance without leaving an immediately dirty preset.
6. Delayed prompt admission errors reveal the editor only while its owner draft and laboratory
   are current; the explicit field-error link continues to navigate.
7. Preset prompt metadata displays `prompt_source_ref` with `prompt_ref` as fallback.
8. Both prompt endpoints document `404 AtomLabErrorResponse`; canonical OpenAPI and CE-kit
   generated types were regenerated.

Focused verification: 213 DB-free API tests and 16 Chromium journeys passed. The latter include
delayed source reads, unavailable/missing/stale sources, successful versus failed/adapted history,
and cancellation/reopen with changed provenance. Connected catalog/history/presets/access API
validation passed 240 tests (overlaps the access cases in the first run). Focused Atom Lab
architecture validation passed 9 tests. Canonical `frontend-check` passed lint, typecheck, all
frontend tests (including 118 Chromium journeys), generated type drift, and production builds.
`validate-docs`, `generate-docs --check`, and `git diff --check` passed.

The full backend/production PostgreSQL and deployment gates remain for CI. They were not repeated:
this fix adds no schema, concurrency, or execution-runtime changes, and the parent already recorded
unrelated ignored-snapshot architecture scans and a Windows Temp ACL full-check limitation.

Regeneration commands (the managed environment owns the backend dependencies):

```powershell
./.quick-check-venv/Scripts/python.exe scripts/agent/runner.py generate-docs
pnpm --filter @anytoolai/ce-kit generate-api-types
```

Windows sandbox tests stalled at SQLite fixtures; the same isolated tests passed outside the
sandbox using `runner.baseline_env()`. Chromium used the installed cache at
`C:/Users/gushinets/AppData/Local/ms-playwright`. The system Python lacks `markdown_it`, so
documentation generation uses the existing managed environment. No dependency was added.
The pnpm update notice request timed out during install; the frozen install and every subsequent
frontend-check step still completed successfully. Test imports used the bundled LiteLLM cost map
(`LITELLM_LOCAL_MODEL_COST_MAP=True`) without any provider call.

## Follow-up review repairs

The independent follow-up found five related defects; all are repaired:

1. The HTML response now sends `Content-Security-Policy: frame-ancestors 'none'`
   alongside its existing no-store policy in both access modes. API regressions
   verify the real headers; Chromium's mocked HTTP contract blocks same-origin and
   cross-origin framing while top-level no-code loading still works.
2. Saved-prompt requests rely on the existing configured UTF-8 byte validator rather
   than a separate 65,536-character ceiling. Boundary tests cover a lower limit,
   65,537-byte ASCII, a raised 70,000-byte limit, and one-byte-over UTF-8/ASCII rejection.
3. Reapplying a configuration preserves only an already known successful trial whose
   snapshot exactly matches the resulting draft. Tests cover successful and failed
   preset readback, later setting changes, and an unknown preset source-run ID.
4. Snapshot comparison reads the retained model selector value even when that model
   has left the catalog. Compatible successful history keeps its trial; admission
   still requires an available model. Failed/adapted history remains unproven.
5. The deployment runbook now limits no-code access to a separately launched API or
   custom local stand and explains that standard Compose and `atom-lab-*` keep code protection.

The canonical exporter shares `components.responses.AtomLabAtomNotFound` across atom
detail and both prompt operations. A regression resolves the three references and
compares the complete schema with live FastAPI, preserving every other response and
the exact error envelope; Markdown retains both prompt 404 entries. Regeneration
removed 14 lines from the generated TypeScript without exclusions, suppressions or
hand-editing generated files. Sonar's final quality-gate decision remains for CI.

Follow-up verification passed: 397 connected API/docs/Atom Lab architecture tests;
canonical `frontend-check` (including all 122 Chromium journeys, lint, typecheck,
Node/Vitest tests, generated type drift and production builds); `validate-docs`;
`generate-docs --check`; and `git diff --check`. A Ruff comparison against HEAD for
all six changed Python files found no new diagnostics and two fewer existing ones.
The focused follow-up regressions failed before fixes at the expected CSP, raised
ASCII-byte limit, preset readback and retired-model boundaries.

The first frontend-check attempt hit the sandbox's pnpm-store symlink permission;
the same canonical command passed with escalation. SQLite tests used the existing
managed interpreter and `runner.baseline_env()` outside the sandbox, with the bundled
LiteLLM cost map. No working DB, provider, deployment, migration, commit or push was used.
