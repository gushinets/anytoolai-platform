# Execution Plan: ANY-721 Next.js web-mirror Security Upgrade

## Status

- State: active
- Owner: agent
- Created: 2026-10-23
- Last updated: 2026-10-26
- Review date: 2026-10-26
- Next action: confirm every check is green on the current PR head, then merge; after merge confirm
  Dependabot #128/#129 are `fixed`.
- Blocker: none

## Goal

Close the Medium `next` Dependabot alerts #128 and #129 (SSG/ISR cache poisoning, GHSA-4jqv-mc3x-m676
and GHSA-mcj8-r9mp-w47p) by raising Next.js in `apps/web-mirror` with pnpm.

## Scope

### In scope

- `pnpm add next@^15.5.28` in `apps/web-mirror`; the lower bound must not admit a vulnerable version.
- Target is 15.5.28, not the 15.5.27 named in the ticket: it is the same 15.5 branch and also fixes
  GHSA-2464-fhr4-w9xw (Critical, Image Optimization API) and GHSA-p3m5-59mp-jv5r (High, Server
  Actions DoS), both affecting `<= 15.5.27`.
- `next@15.5.28` requires `sharp ^0.34.3 || ^0.35.5`; `sharp` 0.35.5 is already on the base since
  PR #201 (ANY-719) merged, so this change does not touch `sharp` or `@img/*`.

### Out of scope

- Next 16, `images: { unoptimized: true }`, ANY-667 (payments-portal), Trivy enforcement.
- The `next>postcss` override stays unchanged.

## Route and cache review

`web-mirror` is an App Router app served by `next start`. It has no `revalidate`,
`generateStaticParams`, `dynamic`/`fetchCache`, `unstable_cache`, `cookies()`/`headers()`, Server
Actions, `next/image` or `images:` config; `next.config.ts` holds only `basePath` and the `/v1/:path*`
rewrite. No cache configuration is added: the fix is the version.

## Validation

- Against `main` after #201, the `pnpm-lock.yaml` diff is +41/-41 and touches only `next` and
  `@next/*`; no `next@15.5.2x` entry remains. `postcss@8.5.31` and the `next>postcss` override are
  unchanged. `pnpm install --frozen-lockfile` passes.
- `next build` route table is identical before and after: `/` and `/_not-found` static, the other
  five routes dynamic; only bundle sizes move by about 1 kB.
- `frontend-check` passes (typecheck, Vitest, build).
- With `dev-up` running: `client-handoff-smoke` 2/2, and `proposal-ai-smoke`, `brief-decoder-smoke`,
  `acceptance-builder-smoke`, `client-update-writer-smoke` pass. Without `dev-up` the handoff smoke
  times out because it needs platform-api.
- `validate-docs` and `generate-docs --check` pass.
- Not run locally: `compose-smoke-prod` and the Trivy SARIF; both run in CI. The review of head
  `d2448b07` confirmed the Trivy SARIF has neither CVE-2026-94484 nor CVE-2026-94543.
- On head `d2448b07` the `proposal-ai-smoke` quota test failed once in CI: "New task" focuses the
  first field one `requestAnimationFrame` later, and when the final fill started before that, the
  experience text landed in the task field and client validation blocked the start. The test now
  waits for that focus (`toBeFocused()`) before filling, as the other product smokes already do;
  `proposal-ai-smoke` passes 10/10 locally with `dev-up`.
