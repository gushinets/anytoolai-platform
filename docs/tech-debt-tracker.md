# Tech Debt Tracker

| ID | Area | Debt | Why accepted | Expiry trigger | Owner |
|---|---|---|---|---|---|
| TD-002 | Artifacts | JSON/text in DB first | no media/files in MVP-A | artifact >1MB or file input | Backend |
| TD-003 | Provider | LiteLLM/fake-provider path first, with provider-policy retry cleanup still active | speed MVP-A | second provider need or provider cost controls | Tech-lead |
| TD-004 | UI | minimal web mirror and CE kit stubs | product validation over polish | first external users | Fullstack |
| TD-007 | Local runtime | Compose project identity and ports are shared across worktrees | single-worktree MVP development | ANY-129 merges | DevEx |
| TD-008 | Diagnostics | logs and context collection are not structured, portable, or privacy-tested | product paths are still forming | ANY-130 merges | Backend |
| TD-009 | Smoke validation | kernel and browser smoke surfaces are placeholders and must not count as evidence | vertical slices are unfinished | the owning feature implements a real journey | Tech-lead |
