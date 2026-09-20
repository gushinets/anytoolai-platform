# Atom Lab browser checks

The fast Node tests execute the production Atom Lab module against a minimal DOM harness. The
Playwright suite exercises the same assets in Chromium, including computed visibility, form
controls, focus transfer, a 375-pixel layout, backend model-capability states, idempotent run
submission, protected polling/reconnection, immutable submitted snapshots, terminal diagnostics,
and safe rendering of successful and contract-invalid provider output.

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
