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

## Publication

Create a codex/any-818 branch, commit only the explicit feature file set, push and create a PR
with the required ANY-818 title and Linear issue section. Add the PR link to the Linear issue
and move it to In Review; do not merge or deploy to production.
