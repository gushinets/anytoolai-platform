# Execution Plan: ANY-721 Next.js web-mirror Security Upgrade

## Status

- State: active
- Owner: agent
- Created: 2026-10-23
- Last updated: 2026-10-23
- Review date: 2026-10-23
- Next action: open the PR "ANY-721 - Update Next.js to 15.5.28 in web-mirror" and confirm
  `compose-smoke-prod` and the Trivy SARIF in CI.
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
- `next@15.5.28` requires `sharp ^0.34.3 || ^0.35.5`, so the lock also moves `sharp` to 0.35.5 until
  PR #201 (ANY-719) lands; whoever merges second regenerates the lock with the same pnpm command.

### Out of scope

- Next 16, `images: { unoptimized: true }`, ANY-667 (payments-portal), Trivy enforcement.
- The `next>postcss` override stays unchanged.

## Route and cache review

`web-mirror` is an App Router app served by `next start`. It has no `revalidate`,
`generateStaticParams`, `dynamic`/`fetchCache`, `unstable_cache`, `cookies()`/`headers()`, Server
Actions, `next/image` or `images:` config; `next.config.ts` holds only `basePath` and the `/v1/:path*`
rewrite. No cache configuration is added: the fix is the version.

## Validation

- `pnpm-lock.yaml` diff is +161/-161 and touches only `next`, `@next/*`, `sharp` and `@img/*`; no
  `next@15.5.2x`, `sharp@0.35.4` or libvips 1.3.3 entry remains. `postcss@8.5.31` and the
  `next>postcss` override are unchanged. `pnpm install --frozen-lockfile` passes.
- `next build` route table is identical before and after: `/` and `/_not-found` static, the other
  five routes dynamic; only bundle sizes move by about 1 kB.
- `frontend-check` passes (typecheck, Vitest, build).
- With `dev-up` running: `client-handoff-smoke` 2/2, and `proposal-ai-smoke`, `brief-decoder-smoke`,
  `acceptance-builder-smoke`, `client-update-writer-smoke` pass. Without `dev-up` the handoff smoke
  times out because it needs platform-api.
- `validate-docs` and `generate-docs --check` pass.
- Not run locally: `compose-smoke-prod` and the CI Trivy SARIF; both run in CI on the PR.
