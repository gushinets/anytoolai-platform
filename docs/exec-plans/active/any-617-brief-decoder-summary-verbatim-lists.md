# ANY-617 Brief Decoder summary fidelity

## Status

- State: active
- Owner: agent
- Created: 2026-11-18
- Last updated: 2026-11-18
- Review date: 2026-11-18
- Next action: Review the verified prompt and fixture changes.
- Blocker: The local baseline requires passwordless sudo for its cross-user permission test.

## Goal

Freelancers can read the extracted facts and questions exactly as supplied and see the readiness verdict in the summary.

## Scope

Update the product prompt, five summary fixtures, upstream Russian and Spanish fixtures, and Python regression tests.

### Out of scope

Separate UI verdict, copy-questions control (ANY-850), and three-run live QA (ANY-591).

## Relevant docs

- [LLM runtime](../../architecture/llm-runtime.md)
- [MVP scope](../../product-specs/mvp-scope-source-of-truth.md)

## Contracts touched

The A10 prompt and fake-provider examples define the document wording within the existing schema.

## Implementation steps

1. Specify copying and localized labels for each section.
2. Align English, Russian, and Spanish fixtures with their upstream results.
3. Compare fixture output against the sources and exercise six regressions.

## Validation

- Targeted Brief Decoder, language policy, captured-source and API tests passed (1,235 cases).
- The freelancer product suite with the quick-check harness tests passed (1,453 cases).
- Documentation validation and generated-document drift checks passed.
- All eight Brief Decoder Playwright smoke cases passed against an isolated fake-provider stack.
- The baseline quick-check reported 4,251 passes, 12 skips, 720 deselections and three
  runner failures. Both Compose status tests passed on retry with the optional local production
  environment file excluded. The cross-user activation-marker test requires passwordless sudo.
- Frontend lint, typecheck and 349 Atom Lab browser cases passed. The web-mirror StrictMode
  draft recovery assertion failed once. All 1,131 web-mirror tests passed on retry. Generated
  API types were current and workspace builds passed.

## Decision log

ANY-761 removed draft_document.v1.md, so Brief Decoder owns its copy rule.
A separate verbatim test preserves the existing A10 guard's independent mutation coverage.

## Progress log

2026-11-18. Verified the ANY-616 base and passed doctor using the managed Python 3.12 environment.
Updated the summary prompt and compared five summary fixtures to their same-run inputs. Added
localized issue and question sources. The six negative cases rejected altered source text.
The existing field-key guard accepts the group labels in all three languages.

The second code review reproduced seven accepted fixture mutations across overview, gaps and
questions. The fixture guard now compares complete ordered sections with their upstream inputs
and selects the reviewed confirmation sentence by language and missing field set. Synthetic
Russian and Spanish examples exercise audience labels because the bakery fixtures omit the
audience. All 1,472 freelancer product and Brief Decoder API bundle tests passed.

## Open questions

Review separate verdict presentation under the UI follow-up.
