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

For the tenth review, limit the scope of a fronted condition to its consequence and
check subsequent assertions in the same sentence. Cover both readiness polarities in
English, Russian and Spanish and exercise the canonical API fixture assertion.

For the ninth review, preserve fronted conditions across commas in the shared fixture readiness check. Verify conditional and unconditional claims in all three languages, including an independent contradiction following a condition.

Round 8: distinguish source items from physical lines, share localized field labels with the provenance check, and exercise multiline copies and labeled identifiers. Keep weak summaries focused on the first clarification. Verify prefixed readiness claims and unrelated explanations in all three languages.

1. Specify copying and localized labels for each section.
2. Align English, Russian, and Spanish fixtures with their upstream results.
3. Compare complete fixture sections with their sources and exercise source-copy and readiness mutations.
4. Apply the same assertions to the seven canonical API documents using recorded A10 inputs.
   Cover empty extractions in all three languages, a dropped issue and a rephrased question.

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

The third code review reproduced a reversed readiness verdict in the fake-provider summary.
The fixture check derives readiness from the three A10 inputs and recognizes explicit verdict
clauses in English, Russian and Spanish. The explanation stays free. Mutation tests exercise
reversed, absent and conflicting verdicts. The signal matrix includes a missing budget with
empty issue and question lists.

The fourth code review found that the Spanish fixture evaluated the summary document and the
test accepted that subject. The five provider fixtures and seven canonical Brief Decoder API
examples now open with an explicit verdict about the brief or request. Both test suites use
the same check, including the prompt's two terms per language and Spanish gender agreement.
The opening-clause convention applies to authored fixtures. Live-generated prose remains
subject to the existing product prompt and separate evaluation. The freelancer product suite,
Brief Decoder API tests and brief-language evaluation tests passed (1,590 cases), as did the
46 web-mirror Brief Decoder tests.

The fifth code review reproduced a missed contradiction when a later verdict ended in a time
qualifier. The fixture guard now matches that verdict at the start of its clause and permits
trailing words after a word boundary. The opening verdict still uses the complete clause.
All seven new regressions failed before the fix and passed afterward. The six language and
polarity combinations also accepted a statement about a different named object with the same
predicate. All 1,597 freelancer product, Brief Decoder API and language evaluation tests passed.

The sixth code review found conflicting A10 instructions for a language mismatch. Extraction,
issue detection and question generation already select the language for the strings they author.
A10 preserves those strings and applies its language check to the text it writes. A Russian
brief with English upstream values now exercises the same source comparison as the five standard
fixtures. A translated goal, deliverable, issue or question fails the regression. All 1,602
freelancer product, Brief Decoder API and language evaluation tests passed.

The seventh code review found that the canonical API replay accepted seven documents whose
sections disagreed with their structured inputs. The shared assertion rejected all seven
original examples. The corrected documents pass against the recorded A10 inputs, including
empty extractions in English, Russian and Spanish. Removing an issue or rephrasing a question
now fails its section check. All 1,604 product, API and language evaluation tests passed,
along with the three web tests that copy the canonical Russian recipe across UI locales.

The eighth review exposed a mismatch between logical source items and physical lines.
A10 now prefixes each item once and preserves internal line breaks. The fixture checks use
the same localized scalar labels when verifying source provenance and comparing sections.
The weak examples now explain the first clarification, and the shared check catches a
verbatim repetition of the entire issue or question list. The readiness check recognizes
explicit fixture verdicts after introductory text in all three languages. It is a check
of authored examples with known verdict wording. Live language quality is evaluated separately.
All 1,626 freelancer product, Brief Decoder API and language evaluation tests passed.

The ninth review reproduced a false contradiction when a comma separated a condition from
its consequence. The fixture verifier now retains that scope and checks the next independent
statement for contradictions. Conditional and unconditional controls cover English, Russian
and Spanish. All 1,632 product, API and language evaluation tests passed.

The tenth review found that a fronted condition stopped the verifier from checking
the rest of the statement. For the authored "condition, consequence" form the verifier
now consumes the consequence and resumes scanning at the next comma. Six regression
cases cover both polarities in all three languages. A seventh exercises the reported
contradiction through the canonical document assertion. All seven reproduced the
failure before the change. All 1,639 product, API and language evaluation tests passed.

## Open questions

Review separate verdict presentation under the UI follow-up.
