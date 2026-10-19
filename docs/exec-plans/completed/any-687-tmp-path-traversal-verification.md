# Execution Plan: ANY-687 tmp Path Traversal Verification

## Status

- State: completed
- Owner: agent
- Created: 2026-10-19
- Last updated: 2026-10-19

## Goal

Confirm that `tmp` < 0.2.6 (GHSA-ph9p-34f9-6g65, CVE-2026-44705) is no longer in the dependency
graph. No code or lockfile change was needed.

## Scope

### In scope

- Verify the lockfile, the frozen install, and `pnpm audit` on `main` (`6a5e53fc`).

### Out of scope

- Restoring `web-ext` browser auto-launch (decided in ANY-677).
- ANY-681 (node-forge) and ANY-683 (adm-zip), tracked in their own tickets.

## Resolution

ANY-677 (#179) upgraded `wxt` 0.20.26 -> 0.21.4, which dropped `web-ext-run`. The chain
`wxt@0.20.26 -> web-ext-run@0.2.4 -> tmp@0.2.5` left the graph. `tmp` had no other parent.

## Verification

- `pnpm-lock.yaml` has no `tmp`, `web-ext-run`, or `web-ext` entries.
- `pnpm install --frozen-lockfile` succeeds.
- `pnpm -r why tmp` and `pnpm -r why web-ext-run` print nothing.
- Stale `node_modules/.pnpm/tmp@0.2.5` and `web-ext-run@0.2.4` directories existed locally from an
  older install. `node_modules/.pnpm/lock.yaml` does not reference them, and a clean install
  removes them.
- `pnpm audit`: no `tmp` advisory. The remaining findings are unrelated to this chain.

### Remaining audit findings (22: 13 high, 9 moderate)

| Package | Severity | Path |
| -- | -- | -- |
| brace-expansion | high, moderate | `ce-kit > openapi-typescript > @redocly/openapi-core > minimatch`, `eslint > minimatch` |
| js-yaml | high | `ce-kit > openapi-typescript > @redocly/openapi-core` |
| postcss, nanoid, source-map-js, sharp | high | `web-mirror > next` |
| next, postcss | moderate | `web-mirror > next` |
| vitest, @vitest/mocker | moderate | `web-mirror > vitest` |

## Not verified in this plan

- Dependabot alert #14 state, CI results on the merge commit, and `frontend-check`.

## Risks

- Adding `web-ext` back reintroduces `tmp`. `web-ext@10.8.0` resolves `tmp@0.2.7`, which is patched.
