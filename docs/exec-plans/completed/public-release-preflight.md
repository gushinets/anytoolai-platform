# Execution Plan: Public web release preflight

## Status

- State: completed
- Owner: agent
- Created: 2026-11-23
- Last updated: 2026-11-23
- Review date: 2026-11-23
- Next action: none.
- Blocker: none.

## Goal

Exercise the enabled product forms on the selected production images before closing public ingress.
Reuse the existing browser happy paths to catch a frontend/API contract mismatch before cutover.

## Steps

- [x] Run the enabled products' existing Playwright happy paths on an isolated Compose project.
- [x] Document image preparation, the gate before maintenance, and how to cover a new product.
- [x] Validate all current cases, an expanded product list, and failure before cutover.

The rehearsal uses disposable PostgreSQL and the bundled fake provider. Live generation and the
production database migration remain separate cutover checks.

## Verification

- Five existing product happy paths passed on the selected images under `/tools`, including
  Task Finder. The Linux browser shared the isolated web container's network namespace to
  work around unavailable Windows Docker Desktop loopback forwarding.
- Targeted runner tests verified product selection, teardown, and rejection of skipped checks
  and external API rewrites. pnpm rejected a missing product workspace.
- Product smoke typecheck and lint, config validation, architecture validation, and docs validation
  passed. A wider Windows runner selection encountered the deployment lock's existing Temp ACL check.
