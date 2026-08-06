# Tech Debt Tracker

| ID | Area | Debt | Why accepted | Expiry trigger | Owner |
|---|---|---|---|---|---|
| TD-002 | Artifacts | JSON/text in DB first | no media/files in MVP-A | artifact >1MB or file input | Backend |
| TD-003 | Provider | LiteLLM/fake-provider path first; retry ownership and the physical-call hard limit are enforced, but broader provider/cost controls remain thin | speed MVP-A | second provider need or provider cost controls | Tech-lead |
| TD-004 | UI | minimal web mirror; CE-kit has a real client/storage foundation but most journey helpers remain stubs | product validation over polish | ANY-171/A18 or first external users | Fullstack |
| TD-009 | Browser smoke validation | dev/prod kernel Compose smoke is real; browser/extension journeys still lack executable smoke evidence | extension vertical slices are unfinished | the owning extension feature implements a real journey | Tech-lead |
