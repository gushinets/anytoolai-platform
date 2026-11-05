# Atom Lab browser checks

The fast Node tests execute the production Atom Lab module against a minimal DOM harness. The
Playwright suite exercises the same assets in Chromium, including computed visibility, form
controls, focus transfer, a 375-pixel layout, backend model-capability states, idempotent run
submission, protected polling/reconnection, immutable submitted snapshots, terminal diagnostics,
safe rendering of successful and contract-invalid provider output, immutable preset versioning,
optimistic-save conflict recovery, concrete-version export, paginated shared history, and explicit
snapshot restoration without a provider call. History checks include running and crash-failed jobs,
nullable runtime IDs, validation-retry success, and unavailable historical model/contract states.

The request-and-response workspace keeps one launch action above the input/prompt editor and
response. Its checks cover keyboard tab switching, compact object-array summaries, error recovery
inside collapsed items, responsive placement, and the distinction between the current draft and
the immutable accepted run. Launching from either editor view records a successful prompt trial;
saving a new Lab prompt preserves its matching source-run provenance. Full input/output schemas,
result JSON, metadata, diagnostic IDs, presets and history remain available.

The shared preset library uses a list and an immutable version card. Browsing a version leaves
the current laboratory draft intact; applying it or starting a new version is explicit. History
uses expandable table rows with Russian status labels, local timestamps, result/request/diagnostic
tabs and complete saved JSON. Library checks also cover empty states, keyboard focus and narrow
layouts while retaining the conflict, unknown-save recovery, export and source-run tests.

Run locally from the repository root:

```bash
pnpm --filter @anytoolai/atom-lab-browser-tests exec playwright install chromium
pnpm --filter @anytoolai/atom-lab-browser-tests test
pnpm --filter @anytoolai/atom-lab-browser-tests lint
pnpm --filter @anytoolai/atom-lab-browser-tests browser
```

`test` runs both the fast Node suite and the real Chromium suite; `browser` remains available for a
focused Playwright rerun. The package is a `pnpm-workspace.yaml` member, so the combined test and
lint commands run through the repository's canonical
`python scripts/agent/runner.py frontend-check`. The `frontend` and required `full-check` workflows
install the pinned Playwright Chromium binary and its operating-system dependencies before invoking
that runner command.
