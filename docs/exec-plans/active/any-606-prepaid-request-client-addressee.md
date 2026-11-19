# Execution Plan: Address the Prepaid Request client directly

## Status

- State: active
- Owner: agent
- Linear: ANY-606
- Created: 2026-11-18
- Last updated: 2026-11-19
- Review date: 2026-11-20
- Next action: review and merge the Prepaid Request addressee rule; live check in ANY-608.
- Blocker: none

## Goal

Address the payer in the second person. Greet them by name when the billing notes identify them, covering the omitted or third-person names reported in ANY-589 A01, A02 and A03.

## Scope

### In scope

Insert one rule after the placeholder instruction in the existing Prepaid Request v1 prompt. Pin its wording and position in a Python test.

### Out of scope

Update, Reply Draft and ProposalAI prompts, payment terms and exclusions (ANY-605), the existing VAT direction rule (ANY-592), and credentialed acceptance (ANY-608). The fake-provider fixtures cover inputs without a named client.

## Relevant docs

- `docs/exec-plans/completed/any-604-prepaid-request-live-acceptance.md`

## Contracts touched

The only configuration change is the text of the existing v1 prompt. API, database, events and frontend contracts retain their current definitions.

## Implementation steps

- [x] Add the supplied rule between the placeholder and speaker instructions.
- [x] Pin its normalized text and relative position in the product suite.
- [x] Extend the live collector with the Prepaid Request form and verify the scenario start and result session in the driver tests.

## Validation

- [x] Run doctor, validate-configs and validate-docs.
- [x] Run quick-check and the addressee, speaker identity, author directions and Client Update Writer product tests.
- [ ] Run full-check when its quick-check prerequisite is green.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-18 | Rule lives only in the Prepaid Request prompt | ANY-606 scopes it to Prepaid Request. ProposalAI already has its own greeting rule. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-18 | Doctor passed using the managed Python 3.12 environment. System Python lacked pytest and pydantic. | Add the rule and run validation. |
| 2026-11-18 | Managed Python doctor, validate-configs and validate-docs passed after the edit. All 90 focused tests passed. | Run broader checks. |
| 2026-11-18 | Freelancer suite passed 1,417 tests on the first run. The remaining wheel packaging test passed on retry with build dependency access. | Record baseline result. |
| 2026-11-18 | quick-check passed config, architecture and documentation validation, including generated docs. Backend pytest reported 4,251 passed, 3 failed, 12 skipped and 720 deselected. | The full-check runner exits on this baseline failure. |
| 2026-11-18 | In test_runner.py, test_prod_stack_running_reflects_compose_ps_output returned invalid Compose environment JSON, test_prod_stack_running_propagates_timeout observed 60 seconds where the mock expected 10, and test_activation_marker_is_readable_by_non_root_api_user required interactive sudo. | Review runner failures separately. |

## Open questions / Follow-up

For ANY-608, follow the [ANY-604 live browser procedure](../completed/any-604-prepaid-request-live-acceptance.md) with provider credentials. Run each case three times through `tests/e2e/client-update-writer-smoke/collect-live.mjs`. In the input JSON set `mode` to `prepaid_request`, supply `billing_context` with string fields `notes`, `amount` and optional `due_date`, and set `tone` for the case. The collector selects Prepaid Request in the web UI and submits those fields. Count the run only after capturing a successful `POST` to `/scenarios/client_update_writer.prepaid_request_v1/start`. Use the returned `scenario_session_id` to identify the output being checked. Verify that the greeting names Елена (A01), Jordan is greeted by name and addressed directly (A02), Никита is greeted in the nominative and addressed as «вы» (A03), and the company-only input gets a greeting without a person's name (A05).
