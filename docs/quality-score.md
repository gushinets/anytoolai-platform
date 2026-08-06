# Quality Score

| Area | Grade | Known gaps | Owner | Last reviewed |
|---|---:|---|---|---|
| Platform Core boundaries | A- | Architecture checks enforce product/LLM/provider import boundaries; still path/text based, not a full package graph. | Tech-lead | 2026-08-05 |
| Config validation | B+ | Current configs and references validate; generated registries are deterministic and current. | Backend | 2026-08-05 |
| Event taxonomy | B+ | Durable events, required dimensions, replay ordering, and correlation tests exist; broader end-to-end coverage belongs to feature work. | Tech-lead | 2026-08-05 |
| Canonical checks and CI | A- | Runner commands and CI share failure-propagating checks; dev/prod Compose jobs exercise a real one-action `kernel_demo` journey. Browser smoke remains feature-owned. | DevEx | 2026-08-05 |
| Repository knowledge | A- | Indexed paths, cross-links, generated-doc freshness, and plan state/location are mechanically checked. | Tech-lead | 2026-08-05 |
| Runtime diagnostics | B+ | API/worker paths emit redacted JSON with available correlation IDs; context collection captures Git, plans, endpoints/status, logs, and failures. | Backend | 2026-08-05 |
| Worktree runtime | B+ | Compose identity, ports, endpoint discovery, readiness, status, and teardown are worktree-scoped with explicit overrides. | DevEx | 2026-08-05 |
| MVP-A1 atom proof | C | Two atoms have strict runnable proof; nine contracts/configs and the aggregate 11/11, 3/3, CLI, result API, and live canary evidence remain planned. | Platform Core | 2026-08-06 |
| CE kit | B- | ANY-170/ANY-171 delivered the tested client/storage and scenario/quota/polling slices; A15c still owns frontend-safe result fetching. | Client Surfaces | 2026-08-06 |
| Handoff model | B+ | Generic backend lifecycle remains Platform Core-owned; A18a-c own CE helpers, web consent, and client smoke without blocking MVP-A1. | Backend / Client Surfaces | 2026-08-06 |
| Web and browser surfaces | C | Result, consent, paywall/onboarding, kernel CE, and browser evidence are explicit MVP-A2 work and are not MVP-A1 gates. | Client Surfaces | 2026-08-06 |
| Generated docs | B+ | API, config, action, event, and runtime-schema docs are deterministic and current; presentation remains intentionally minimal. | Tech-lead | 2026-08-05 |
