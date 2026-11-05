# Execution Plan: Atom Lab presets and history layout

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: none
- Blocker: none

## Scope

Implement the approved list-and-detail layout for presets and an expandable table for run
history. Keep the existing Atom Lab visual language, full technical data and complete JSON.
Make the all-atoms scope explicit and keep browsing a saved immutable version separate from
editing a new version or creating a preset from the current draft or a historical run.

Preserve pagination, export, conflict/unknown-save recovery, contract compatibility and
adaptation, unsaved-change guards, run restore and source-run provenance. Reuse current API
contracts and response rendering. Do not change provider execution or database definitions.

## Design

Use existing white surfaces, dark text (#172033), indigo actions (#2638b8), muted text
(#5f6b85), and subtle dividers (#dfe4ee). Selected-list metadata uses #4d5b76 to keep
contrast above 4.5:1 on #e7eaff. Retain the system sans-serif and monospace only
for technical identifiers and JSON. Presets use a compact list beside a read-only detail
card, with an explicit edit action. History uses semantic table rows and inline details;
status, local date/time, atom and model identify a run before opening it. Expanded details
add reasoning, duration and the result/request/diagnostic sections.
Both libraries occupy the workspace without an unrelated selected-atom sidebar. At narrow
widths reflow the preset columns and history rows without horizontal clipping.

## Steps

1. Read the current state transitions, API parsers, response renderer and browser fixtures.
2. Restructure markup and rendering while retaining existing persistence/recovery behavior.
3. Add focused regressions, run Node/Chromium suites, lint and documentation checks.
4. Rebuild the existing loopback-only Docker stack without deleting data. Inspect both
   screens visually on desktop and mobile using saved real presets and run responses.
5. Record results and limits and move the completed plan to completed/.

## Verification

The standard test command passed 53 Node tests and 96 Chromium journeys. A focused
pagination regression also passed after the final change that keeps a selected older run
collapsed while its row is outside the currently loaded page. Lint and diff checks passed.

The rebuilt local stack retains the existing PostgreSQL volume, loopback ports (18104 API,
15536 PostgreSQL) and explicitly disabled local access code. JavaScript and CSS served from
Docker were compared byte-for-byte with the working sources; HTML matches after the existing
server-owned local-access attribute injection.

Live browser checks read the two real preset identities and saved successful/failed runs.
They verified exact immutable version JSON, version switching, concrete-version export,
new-version cancellation, result/request/diagnostic JSON, history pagination, restore to a
draft and save-from-history provenance. No API writes, new runs or paid provider calls were
made. Preset and run lists were compared before and after the checks.

Inspected actual desktop, new-version, successful-run, failed-run, diagnostic and mobile
screenshots. Checked 1440px desktop plus 1024px, 768px, 390px and 320px layouts; no document
overflow or out-of-bounds controls were found. The history accessibility audit passed with
zero violations. The selected-preset audit caught a 4.48:1 muted-text contrast issue, which
was corrected in the final API-image rebuild. The final visible selected-card and new-version
form audits passed with zero violations (22 and 23 checks respectively). API, worker and
PostgreSQL are healthy; local access remains open without a code.

Full backend/full-check and new provider generations are not part of this UI-only change.
