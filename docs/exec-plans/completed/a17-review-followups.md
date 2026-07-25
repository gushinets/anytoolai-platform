# Execution Plan: A17 Review Follow-ups

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Review date: 2026-07-22
- Next action: none
- Blocker: none

## Goal

Apply the still-valid A17 review findings with minimal changes: repair the handoff lifecycle Markdown
table, strengthen handoff mapping validation/error identity, and make compatibility revision `0008`
self-contained.

## Verified findings

- [x] Lifecycle table state unions contain unescaped pipes.
- [x] Source mappings ending in a dot are currently accepted and mapping errors omit handoff identity.
- [x] Revision `0008` dynamically imports sibling revision `0004` at runtime.

## Implementation and validation

- [x] Escape literal state-union pipes without changing table content.
- [x] Reject trailing-dot source paths and attach handoff identity to all mapping shape errors.
- [x] Inline the canonical `product_handoffs` schema in revision `0008` while retaining its guard.
- [x] Add focused config validation coverage and run config, migration, docs, and baseline checks.

## Validation result

- Focused review cases: 6 passed.
- Full config-loader module: 30 passed.
- Full runtime-storage module: 38 passed.
- Canonical DB-free aggregate: 326 passed, 3 deselected.
- Config, architecture, docs, generated-doc freshness, formatting, clean-file lint, and diff checks passed.
