# Atom Lab browser checks

The fast Node tests execute the production Atom Lab module against a minimal DOM harness. A focused
Playwright scenario exercises the same assets in Chromium, including computed visibility, form
controls, focus transfer, and a 375-pixel layout.

Run locally from the repository root:

```bash
pnpm --filter @anytoolai/atom-lab-browser-tests test
pnpm --filter @anytoolai/atom-lab-browser-tests lint
pnpm --filter @anytoolai/atom-lab-browser-tests browser
```

The package is a `pnpm-workspace.yaml` member, so both commands are also included in the repository's
canonical `python scripts/agent/runner.py frontend-check` recursive test and lint passes. The
Chromium scenario remains an explicit browser check because it requires an installed Playwright
browser binary.
