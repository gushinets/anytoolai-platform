# Execution Plan: Handoff Event Lineage Integrity

## Status

- State: completed
- Owner: agent
- Created: 2026-07-23
- Last updated: 2026-07-23
- Review date: 2026-07-23
- Next action: none
- Blocker: none

## Goal

Keep canonical handoff lineage protected from caller properties while ensuring source events carry
known source job/artifact dimensions and target events correlate only to target runtime rows.

## Plan

- Verify the shared handoff event builder and every handoff/quota call site.
- Separate source-side context defaults from explicit target-side correlation.
- Add event-chain assertions for protected properties, source lineage, accepted target lineage, and
  consumed target job lineage.
- Clarify the event-taxonomy contract and run focused handoff/event tests plus repository checks.

## Validation result

- Focused handoff and event tests: 40 passed.
- Ruff lint and format checks passed.
- Documentation, architecture, and generated-document checks passed.
- Canonical quick-check: 337 passed, 5 deselected.
