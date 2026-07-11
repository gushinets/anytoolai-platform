# Tech Debt Tracker

| ID | Area | Debt | Why accepted | Expiry trigger | Owner |
|---|---|---|---|---|---|
| TD-002 | Artifacts | JSON/text in DB first | no media/files in MVP-A | artifact >1MB or file input | Backend |
| TD-003 | Provider | LiteLLM/fake-provider path first, with provider-policy retry cleanup still active | speed MVP-A | second provider need or provider cost controls | Tech-lead |
| TD-004 | UI | minimal web mirror and CE kit stubs | product validation over polish | first external users | Fullstack |
| TD-005 | Generated docs | generated docs are refreshed manually and OpenAPI helper is still placeholder-level | speed MVP-A | generated docs differ from current schema/API/config contracts | Tech-lead |
