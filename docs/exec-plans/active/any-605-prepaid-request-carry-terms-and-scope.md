# Execution Plan: Prepaid Request payment terms and scope

## Status

- State: active
- Owner: agent
- Created: 2026-11-19
- Last updated: 2026-11-20
- Review date: 2026-11-20
- Next action: ANY-608 live acceptance on A01/A02/A03/A05 + S5
- Blocker: none

## Goal

Every payment condition and scope boundary stated in Prepaid Request notes reaches the client message.
A percentage-only amount is resolved against its agreed base.

## Scope

### In scope

The Prepaid Request compose prompt and its Python product contract tests.

### Out of scope

Workflow, schema and model changes. ANY-608 owns live acceptance.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/product-specs/freelancer-suite-v0.md`
- `docs/exec-plans/completed/any-604-payment-terms-retention.md`

## Contracts touched

- Config: `client_update_writer.prepaid_request_compose_persuasive_text.v1` prompt text only.
- API, DB, Events, Frontend: none.

## Reproduction

| Lost in QA | Case | Coverage before ANY-605 |
|---|---|---|
| Stated remaining balance **amount** ("Remaining net EUR 1,440 after approval", "остаток 53 527,50 RUB после приёмки") | A02, A05 | Only *when* the balance is payable. The amount is not named, and "Do not calculate an unstated balance" can read as "leave balances out". |
| Scope exclusions ("Extra illustrations and source AI files are excluded", "Копирайтинг не входит") | A02, A05 | **None.** The words "exclusion" and "scope" do not appear in the prepaid prompt. The sibling `update_compose_reply.v1.md` does have a "scope exclusions" rule (ANY-624/628). |
| Conditions for starting the work and timeline counting ("Work starts after deposit and reference images are received"; "срок 8 рабочих дней отсчитывается только после выполнения обоих условий") | A02, A05 | None. They survive by chance. |
| Tax treatment stated as a term ("НДС не начисляется", distorted to "НДС не начинается") | A05 | None. |
| Amount given only as a share: `amount: "предоплата 50%"`, notes: "согласованный бюджет 90 000 рублей… остаток оплачивается после сдачи макета" | S5 (production 2026-11-11) | None. Rule D says state "`context.amount`" exactly as given, so the model wrote "предоплата в размере 50% от согласованного бюджета — 90 000 рублей". This is ambiguous: 45 000 ₽ is never named, and the balance condition was dropped. Step 2's currency bullet ("a currency named only for other amounts … does not count") can also wrongly treat a percentage amount as having no currency. |

Exact S5 production input/output, decoded from the ANY-851 attachment "Production 11.11.2026 — входы и ответы 11 прогонов":

```
billing-amount:   "предоплата 50%"
billing-due-date: "в течение 4 дней"
billing-notes:    "Новый проект, согласованный бюджет 90 000 рублей. Предоплата нужна для бронирования времени команды. Согласовано, что остаток оплачивается после сдачи макета."
tone: warm, language: ru
result: "Для бронирования времени команды нужна предоплата в размере 50% от согласованного бюджета — 90 000 рублей. Пожалуйста, внесите её в течение 4 дней и сообщите, когда отправите оплату."
```

The deployed revision of S5 is unknown.

## Implementation steps

- [x] Inspect the local environment with doctor.
- [x] Update payment attribution, routing, term retention and confirmation priorities.
- [x] Add Python contract tests and verify the registered prompt.
- [x] Run repository validation and record the live smoke status.

## Validation

- Doctor passed with the managed Python 3.12.13 environment. The system interpreter lacks pytest and Pydantic.
- All 106 targeted tests passed across the product, author-direction, speaker-identity and API bundle modules.
- Configuration, architecture, documentation and generated-document checks passed.
- The local Compose project had no running services. Live acceptance is deferred to ANY-608.

Canonical quick-check: 4,251 passed, 3 failed, 12 skipped, 720 deselected. All three failures were in
`tests/test_runner.py`:

- `test_prod_stack_running_reflects_compose_ps_output` returned a mocked container ID where the
  local production environment file triggered a Compose configuration query expecting JSON.
- `test_prod_stack_running_propagates_timeout` expected 10 seconds for the stack query and saw
  the environment query's 60-second timeout first.
- `test_activation_marker_is_readable_by_non_root_api_user` failed with
  “sudo: interactive authentication is required”.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-19 | Follow author directions such as “do not calculate tax” without repeating them. | Only deal terms stated as facts belong in the client message. |
| 2026-11-19 | Compute a deposit from its share and agreed base. | The notes determine the deposit. A later balance requires an explicit figure. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-19 | Traced the single prepaid compose step to the registered v1 prompt. | Run doctor and update the prompt. |
| 2026-11-19 | Updated attribution, confirmation and request wording, and added three tests against the registered prompt. | Validate the API bundle and repository baseline. |
| 2026-11-19 | Verified all 106 targeted tests and recorded three runner failures in the broader baseline. | ANY-608 live acceptance on A02/A03/A05 + S5. |
| 2026-11-19 | Routed shares requiring rounding to terms confirmation and checked the one-third of USD 100 example. All 91 product and shared-prompt tests, config and documentation checks passed. | ANY-608 live acceptance. |

## Fractional deposit review

The input schema accepts a fraction in the amount field and deal terms in free-text notes.
Resolve both to one payable deposit before checking conflicts, receipts or the amount still due.
Cover the exact share, an agreed rounded figure, a rounding convention alone, and missing or
conflicting rounding terms in the product prompt contract.

All 107 targeted product, shared-prompt and API bundle tests passed after the change.
Doctor, config validation, documentation validation and the whitespace check passed.
ANY-608 retains live verification of generated messages.

On 2026-11-20 the share rule was updated to use the agreed base and currency across the amount
field and notes. The A01 balance trigger was added to the live checklist in ANY-608.

## Open questions

None for implementation.

## Follow-up debt

ANY-608 live acceptance on A01/A02/A03/A05 + S5. Each of the three A01 messages must greet
Елена by name and state that the balance is payable after delivery of both the final PDF and PPTX.
