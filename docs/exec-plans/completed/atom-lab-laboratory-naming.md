# Execution Plan: Atom Lab Laboratory naming

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: none
- Blocker: none

## Scope

Use «Лаборатория» for the main Atom Lab workspace and its navigation/actions, including
preset application, run restoration, return links, empty states, source hints and status
messages. The history action explicitly restores a request. Align current product docs.
Keep existing DOM identifiers and API contracts compatible with callers and tests.

## Verification

Search all repository source for the retired Russian label and grammatical forms. Run the
existing Atom Lab tests, lint and documentation checks. Rebuild the local API image while
retaining PostgreSQL data and the configured local access. Check actual desktop/mobile labels
and wrapping in the browser using saved presets/runs without paid requests.

## Results

Replaced all ten user-facing occurrences in static markup and runtime messages. Navigation
uses «Лаборатория»; actions use «Открыть в лаборатории», «В лабораторию» and
«Восстановить запрос в лаборатории». Repository source search found no remaining retired
Russian label. Current product documentation and the browser-suite README use the new name.

Existing 53 Node tests and 96 Chromium journeys passed, as did lint, documentation validation
and diff checks. Rebuilt the local API image and verified its served assets against source.
API, worker and PostgreSQL remain healthy with loopback access and the existing data volume.

Live checks asserted the new labels, source/status text, preset application and history
restoration. Inspected desktop and mobile screenshots and checked widths 1024, 768, 390
and 320px without horizontal overflow or controls outside the screen. Saved preset/run
lists were unchanged; no API writes, browser errors or provider calls occurred during QA.
