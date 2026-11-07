# Execution Plan: Atom Lab Workbench

## Status

- State: completed
- Owner: agent
- Created: 2026-11-05
- Last updated: 2026-11-05

## Scope

- Keep the Atom Lab contract and worker execution path. List compatible platform and product
  prompts from the active registry and allow run-local edits.
- Store named Lab prompts in PostgreSQL, scoped by tenant, region and atom. Record their source
  and optionally an exact successful test run. Preserve source provenance in the run snapshot.
- Put run controls above the editor and result. Keep the contract, JSON input, full validated
  JSON result, failed raw response, presets and history available.

## Verification

- Cover protected listing, saving, contract checks and run provenance in focused tests.
- Rebuild the local Compose stack with its existing database and verify the editor workflow in
  a browser, including a real provider run and reopening the saved prompt.

Repository doctor, Atom Lab API and storage tests, 52 Node tests, 88 Chromium journeys, lint,
architecture and generated contract checks passed.

The Compose stack on port 18104 applied migration 0016 to the existing database. The browser
loaded the platform and Client Update Writer prompts for A07. An edited product prompt passed
the contract with GPT-5.4 mini at medium reasoning and was saved with its source run. After
rebuilding Compose, the saved prompt was reopened and passed a second real run with the exact
saved text. The browser displayed the full JSON result, and the narrow view fit a 390px viewport.
