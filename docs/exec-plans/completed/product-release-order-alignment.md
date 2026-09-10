# Execution Plan: Product Release Order Alignment

## Status

- State: completed
- Owner: agent
- Linear: [ANY-452](https://linear.app/paveldik/issue/ANY-452/align-mvp-b-documentation-with-the-five-product-release-order)
- Created: 2026-09-08
- Last updated: 2026-09-08
- Review date: 2026-09-08
- Next action: none; release-order documentation is aligned.
- Blocker: none for the release-order update.

## Goal

Align all current product delivery documents with the user-approved order:
ProposalAI, Client Message Decoder, Scope Creep Guard, Send-Ready, Brief Decoder.
Use the names and atom chains in `docs/product-specs/atom-ready-product-inventory.md`.

## Scope

Documentation only: controlling scope, product specs, inventory/backlog, architecture overview,
ADR, web design, and planning references. Preserve historical logs with a supersession note.
No runtime, API, DB, config, or bulk Linear planning changes. The follow-up publication request
adds the tracking issue ANY-452 and a linked PR, reusing existing product tickets.

## Relevant docs

- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/atom-ready-product-inventory.md`
- `docs/adr/0008-web-first-multi-product-host.md`

## Implementation steps

- [x] Align the five-product order, names, atom chains, and user-supplied priority rationale.
- [x] Align backlog, reuse proof, handoff dependencies, and historical planning references.
- [x] Review the diff and run documentation checks.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py quick-check` before PR: 1191 passed, 3 skipped, 399 deselected
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `.quick-check-venv/Scripts/python.exe scripts/agent/runner.py generate-docs --check`
- [x] `git diff --check`, stale-order search, and exact five-name/order assertions across four product specs

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-08 | Replace the six-product validation set with the five products in the approved order. | User prioritizes pain frequency, fear of mistakes, previously checked demand, and broad project value. |
| 2026-09-08 | Keep Brief Decoder to Acceptance Builder as a later handoff candidate. | Acceptance Builder is outside the new initial release set; do not invent a replacement mandatory pair. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-08 | Located controlling and duplicated order statements; doctor passed. | Update and validate documentation. |
| 2026-09-08 | Aligned 11 existing documents and verified all four product-spec orders. Documentation validation passed. System Python generated OpenAPI drift in ValidationError fields; the repository-managed Python environment passed the generated-doc check without file changes. | None for this documentation task. |

## Open questions

None for the release-order update. Product-specific activation contracts for the two promoted
products belong to their bundle specifications before implementation.

## Follow-up debt

Existing Linear issue structure needs a separate audit; this task changes repository docs only.

Existing product tickets were checked before PR creation; do not create duplicate product issues:

| Release order | Inventory product | Existing parent | Bundle/workflow | Web E2E/QA |
|---|---|---|---|---|
| 1 | ProposalAI | ANY-35 | ANY-227 | ANY-243 |
| 2 | Client Message Decoder | ANY-416 | ANY-423 | ANY-431 |
| 3 | Scope Creep Guard (currently Scope Guard in Linear) | ANY-9 | ANY-229 | ANY-245 |
| 4 | Send-Ready | ANY-12 | ANY-230 | ANY-246 |
| 5 | Brief Decoder | ANY-27 | ANY-232 | ANY-248 |

The Freelancer Suite project description still contains the previous release set. Client Update
Writer bundle work already has PR #103; account for that existing work in any subsequent Linear
planning alignment. This documentation PR does not change or cancel those tickets or PRs.
