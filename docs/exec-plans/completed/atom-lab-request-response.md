# Execution Plan: Atom Lab request and response workspace

## Status

- State: completed
- Owner: agent
- Created: 2026-11-05
- Last updated: 2026-11-05

## Scope

Implement the approved request-and-response layout: one launch panel above a tabbed request
editor and the response, with distinct input form/JSON controls. Keep one prompt editor and
one launch action, retaining prompt trials and save-as-new provenance. Compact object items
without hiding validation failures. Clearly distinguish the current draft from an accepted
run and its immutable configuration.

Preserve all contracts, complete JSON, diagnostic metadata, model capability handling,
submission retries, presets, shared history and prompt saving. Keep the existing local access
configuration. Do not change backend contracts or make new paid provider calls.

## Verification

Add focused browser regressions for layout, draft/run differences, keyboard navigation,
collapsible fields, validation recovery and prompt saving through the shared launch action.
Run the Atom Lab Node and Chromium suites, lint, documentation validation and diff checks.
Rebuild the existing local Docker stack, inspect the actual interface visually on desktop and
mobile, and use existing run history to verify real response and snapshot rendering.

Implementation and automated checks are complete: 53 Node tests, 93 Chromium journeys and lint
passed. Focused regressions cover keyboard navigation, initial validation, collapsed-item error
recovery, form/JSON roundtrips, the shared launch/prompt-save workflow and immutable responses.

Rebuilt the local Docker stack; API, worker and PostgreSQL are healthy. Verified the live schemas
and example form/JSON roundtrips for all 11 atoms. Visually inspected the actual input editor,
prompt editor and response on desktop and mobile. Confirmed no horizontal overflow at 390px and
320px, readable hover contrast on the launch button, and no browser script errors.

For the successful response view, restored an existing A06 run on gpt-6.1-sol and intercepted
the browser's launch acknowledgement to replay that saved run. The response and metadata were
read from the real API; no new run was created. Verified full result JSON, diagnostic IDs and
the immutable submitted configuration, including the warning after editing the prompt. No
provider calls, new Lab prompt writes or other backend mutations were made during live QA.
