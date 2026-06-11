# Architecture Index

Read these in order for MVP-A/MVP-B source alignment:

1. `platform-boundaries.md` — product-neutral kernel and MVP-B boundary.
2. `package-layering.md` — allowed dependency direction.
3. `config-model.md` — repo definitions vs PostgreSQL runtime state.
4. `scenario-session-model.md` — required scenario session fields and statuses.
5. `workflow-model.md` — minimal workflow runner support and exclusions.
6. `action-model.md` — all 11 product-neutral action types.
7. `provider-gateway.md` — provider/model boundary and call metadata.
8. `structured-output.md` — schema validation and raw-output debugging artifact.
9. `event-taxonomy.md` — MVP-A platform events and dimensions.
10. `quota-model.md` — guest quota and email/paywall conversion path.
11. `handoff-model.md` — backend-owned source-to-target session transfer.
12. `frontend-boundaries.md` — CE/web mirror limits and shared `ce-kit`.
