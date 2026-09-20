# Atom Lab browser checks

The fast Node tests execute the production Atom Lab module against a minimal DOM harness. A focused
Playwright scenario exercises the same assets in Chromium, including computed visibility, form
controls, focus transfer, and a 375-pixel layout.

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
