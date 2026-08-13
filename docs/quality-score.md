# Quality Score

| Area | Grade | Known gaps | Owner | Last reviewed |
|---|---:|---|---|---|
| Platform Core boundaries | A- | Architecture checks enforce product/LLM/provider import boundaries; still path/text based, not a full package graph. | Tech-lead | 2026-08-13 |
| Config validation | B+ | Current configs and references validate; generated registries are deterministic and current. | Backend | 2026-08-13 |
| Event taxonomy | B+ | Durable events, required dimensions, replay ordering, and correlation tests exist; broader end-to-end coverage belongs to feature work. | Tech-lead | 2026-08-13 |
| Canonical checks and CI | B+ | Backend gates and Ubuntu frontend CI are failure-propagating; Windows `full-check` currently fails to launch the extensionless `openapi-typescript` shim, and Windows frontend CI/Node-major policy are absent. | DevEx | 2026-08-13 |
| Repository knowledge | A- | Indexed paths, cross-links, generated-doc freshness, and plan state/location are mechanically checked. | Tech-lead | 2026-08-13 |
| Runtime diagnostics | B+ | API/worker paths emit redacted JSON with available correlation IDs; context collection captures Git, plans, endpoints/status, logs, and failures. | Backend | 2026-08-13 |
| Worktree runtime | B+ | Compose identity, ports, endpoint discovery, readiness, status, and teardown are worktree-scoped with explicit overrides. | DevEx | 2026-08-13 |
| MVP-A1 atom proof | B- | All 11 action types are registered and seven have strict product-configured standalone runtime paths. Four strict atom slices plus aggregate 11/11, 3/3, CLI, and live-canary evidence remain; the frontend-safe result API is delivered. | Platform Core | 2026-08-13 |
| CE kit | B | A15a-c deliver tested identity/storage, scenario/quota/polling, and frontend-safe result fetching. Handoff, email-capture, and client-event helpers remain separately owned deferred slices. | Client Surfaces | 2026-08-13 |
| Handoff model | B+ | Generic backend lifecycle remains Platform Core-owned; A18a-c own CE helpers, web consent, and client smoke without blocking MVP-A1. | Backend / Client Surfaces | 2026-08-13 |
| Web and browser surfaces | C | Result, consent, paywall/onboarding, kernel CE, and browser evidence are explicit MVP-A2 work and are not MVP-A1 gates. | Client Surfaces | 2026-08-13 |
| Generated docs | B+ | API, config, action, event, and runtime-schema docs are deterministic and current; presentation remains intentionally minimal. | Tech-lead | 2026-08-13 |
