# Quality Score

| Area | Grade | Known gaps | Owner | Last reviewed |
|---|---:|---|---|---|
| Platform Core boundaries | A- | `validate_architecture.py` and architecture tests enforce product/LLM/provider import boundaries; still path/text based, not a full package graph. | Tech-lead | 2026-07-15 |
| Config validation | B+ | Current configs and references validate; generated-registry freshness is tracked by ANY-128. | Backend | 2026-07-15 |
| Event taxonomy | B | Durable event log, emitter, required dimensions, and runtime service tests exist; broader end-to-end event coverage belongs to feature work. | Tech-lead | 2026-07-15 |
| Canonical checks and CI | B+ | Runner commands, locked frontend compilation, and CI use the same failure-propagating interface; feature-owned smoke coverage remains deferred until real slices exist. | DevEx | 2026-07-15 |
| Repository knowledge | A- | Indexed paths, required cross-links, active-plan metadata, and plan state/location are enforced locally and in CI. | Tech-lead | 2026-07-15 |
| Runtime diagnostics | B+ | Existing API/worker paths emit redacted JSON with available correlation IDs; cross-platform context collection captures Git, plans, runtime endpoints/status, logs, and failures. | Backend | 2026-07-15 |
| Worktree runtime | B+ | Compose identity, host ports, endpoint discovery, readiness, status, and teardown are worktree-scoped with explicit overrides. | DevEx | 2026-07-15 |
| CE kit | C- | Required function surface exists, but implementations are demo stubs and need real API integration. | Fullstack | 2026-07-15 |
| Handoff model | C- | Config contracts and event/storage dimensions exist; backend token flow and web consent remain placeholder-level. | Backend | 2026-07-15 |
| Generated docs | B+ | API, config, action, event, and runtime-schema docs are deterministic and checked against canonical sources; presentation remains intentionally minimal. | Tech-lead | 2026-07-15 |
