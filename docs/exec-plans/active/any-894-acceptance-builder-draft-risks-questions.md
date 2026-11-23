# Acceptance Builder Draft risks and client questions (ANY-894)

## Status

- State: active
- Owner: agent
- Linear: ANY-894
- Created: 2026-11-23
- Last updated: 2026-11-23
- Review date: 2026-11-30
- Next action: Verify the Draft output and review live evidence.
- Blocker: none identified.

## Goal

Show grounded risks, conflicting statements and concrete questions before agreeing acceptance criteria.

## Scope

Acceptance Builder Draft workflow, schema, prompt rules, renderer contract, web parser and
presenter, multilingual fixtures, regression suite, API and browser smoke tests, product docs.
Check retains its original extraction instructions and copy. Draft passes the contradiction
instruction in its A01 field description. This keeps a single extraction prompt.

## Implementation plan

1. Capture pre-change results for the two reported briefs.
2. Detect issues against the original brief and conditionally generate questions.
3. Render structured results in analysis-language order in recap and copy.
4. Exercise fixtures, multilingual controls, live runs and repository checks.

## Validation

The managed Python 3.12 environment passed doctor.
