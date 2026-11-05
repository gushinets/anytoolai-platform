# Execution Plan: ANY-818 Atom Lab Laboratory delivery

## Status

- State: active
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: review the linked PR and required GitHub CI
- Blocker: none

## Goal

Deliver the accumulated Atom Lab prompt editor, saved prompts, compact request/response UI,
preset/history redesign and Laboratory naming under
[ANY-818](https://linear.app/paveldik/issue/ANY-818/atom-lab-redaktor-produktovyh-promptov-i-interfejs-laboratoriya).

## Scope

Include Atom Lab production changes, migration, generated contracts, feature tests and the
November feature plans. Leave unrelated product reports and earlier experiments out of this PR.
Preserve the default protected surface, local operator opt-out and existing provider boundary.

## Integration

The tested local base was 2b492099. Current origin/main is 4cd2e0aa and already owns migrations
0016 and 0017 for execution metering. Renumber the saved-prompt migration to 0018 after 0017,
retain both sets of schema/API changes and regenerate derived docs/contracts after integration.
The running local acceptance DB has the old development revision numbering; it must not be
stamped or migrated as part of publishing the PR. Prove a clean upgrade on an isolated test DB.

## Verification

Previous feature checks: 53 Node tests, 96 Chromium journeys, lint, live Docker desktop/mobile
inspection and zero-write saved-run verification. Run repository and migration checks on the
integrated branch, record exact results and disclose any unresolved limitations in the PR.

The branch is based on 4cd2e0aa with migration 0018 after 0017. Generated docs and API types
are current. Canonical frontend-check passed, as did the Atom Lab DB-free API/Core suite and
five PostgreSQL storage/migration/concurrency tests. The latter use disposable databases and
cover saved-prompt replay plus tenant/region/atom isolation. A clean checkout passed all 242
architecture tests after updating the atom-ID drift guard for the label-derived catalog.

Windows full-check was attempted but did not complete successfully. Local ignored QA snapshots
cause four provider-boundary failures in the working folder; those pass in the clean checkout.
The unchanged deployment runner test also fails on the local Temp ACL before its selector
assertion. No permissions or lock-safety rules were changed. Full required CI remains pending.

## Independent review round 1

Reviewer: GPT-6.1 Sol (`gpt-6.1-sol`), xhigh; reviewed head `b038fb055dabeb345b067d952214b2c6c4cca5cb`.
All three findings were confirmed and repaired:

- P1: update both current-head assertions to 0018; reflect the historical 0016 schema and assert
  the exact 0016-to-0017 data transition before upgrading the disposable database to current head.
- P2: retain prompt origin through history restoration, preset create/version/apply/export and
  subsequent submissions. Optional preset `prompt_source_ref` is stored by migration 0018;
  existing presets remain valid with null provenance. New writes validate the referenced prompt
  against the current atom and tenant/region scope.
- P2: a saved prompt's successful trial must match both input/output schema references and versions.
  Tests also cover valid evidence and cross-tenant/cross-region rejection.

Validation: doctor passed; 291 focused API/Core tests passed; all eight targeted PostgreSQL tests
passed (the three reported migration regressions plus five Atom Lab migration/storage/concurrency
tests). Canonical frontend-check passed, including 53 Node tests and 97 Chromium journeys.
The added parser compatibility/negative assertions and three prompt-origin browser journeys also
passed after the final test edits. Documentation validation and generated-document drift passed.
All database checks use UUID-named disposable databases via the container's `/postgres` maintenance
database; the acceptance application database was not migrated or stamped. No provider was called.

The canonical PostgreSQL run completed with two failures and three teardown errors, all connection
timeouts or unexpected connection closure. The affected cases were:

- `test_failed_0016_migration_rolls_back_ddl_counters_and_version_then_retries` (failed while
  seeding 0015, before exercising the migration).
- `test_client_event_rejects_uppercase_mode_value` (connection closed during identity lookup).
- Teardown of `test_paid_counter_constraints[values0]`,
  `test_workflow_runner_output_mapping_passes_scenario_input_through_verbatim`, and
  `test_unavailable_final_candidate_never_consumes_or_publishes[provenance]`.

All five cases passed in a 12-test retry alongside the full targeted migration/Atom Lab PG set.
The two existing POSIX-only SIGTERM tests were skipped on Windows. Three disposable databases
left by failed teardowns were individually verified inactive and removed by exact UUID name.
The broad PostgreSQL command remains a non-green local run; required GitHub CI must confirm it.
Local diagnostics: `.quick-check-tmp/fix-round1-postgresql.log` and
`.quick-check-tmp/fix-round1-pg-retry.log` (ignored test artifacts, not PR content).

The next reviewers must inspect the same resulting commit: fresh GPT-6.1 Sol xhigh, then GPT-6 Sol
xhigh (the user-approved replacement for unavailable GPT-5.6). Leave PR 259 open and do not merge.

## Publication

Create a codex/any-818 branch, commit only the explicit feature file set, push and create a PR
with the required ANY-818 title and Linear issue section. Add the PR link to the Linear issue
and move it to In Review; do not merge or deploy to production.
