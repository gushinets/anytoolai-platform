# Handoff Model

Handoff is backend-owned and user-confirmed.

Flow:

1. Source scenario creates handoff token.
2. Web mirror shows consent preview.
3. User accepts.
4. Backend creates target scenario session.
5. Event log links source session, handoff, and target session.

No direct trusted CE-to-CE raw data transfer.

MVP-A handoff state stores:

- `handoff_token`;
- source product/frontend/session/artifact;
- target product/frontend/scenario;
- target scenario session after acceptance;
- consent requirement and accepted timestamp;
- creating and accepting guest IDs;
- context payload;
- created and expiry timestamps.

Statuses:

- `created`
- `viewed`
- `accepted`
- `declined`
- `consumed`
- `expired`
- `failed`

MVP-A only needs a smoke handoff inside `kernel_demo`. Real Freelancer handoff maps begin in MVP-B.
