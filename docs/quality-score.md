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
| CE kit | C+ | ANY-170 added the tested API client, async storage, guest identity, runtime config, and OpenAPI drift checks; quota, scenario start, polling, artifacts, events, email, and handoff remain deferred/stubbed. | Fullstack | 2026-08-05 |
| Handoff model | B+ | Generic backend token lifecycle, guarded persistence, safe previews, linked immediate/deferred sessions, event correlation, API and worker-lineage tests are implemented; A18 owns the web/CE consent surface. | Backend | 2026-08-05 |
| Generated docs | B+ | API, config, action, event, and runtime-schema docs are deterministic and current; presentation remains intentionally minimal. | Tech-lead | 2026-08-05 |
