# Tech Debt Tracker

| ID | Area | Debt | Why accepted | Expiry trigger | Owner |
|---|---|---|---|---|---|
| TD-002 | Artifacts | JSON/text in DB first | no media/files in MVP-A | artifact >1MB or file input | Backend |
| TD-003 | Provider | LiteLLM/fake-provider path first; retry ownership and the physical-call hard limit are enforced, but broader provider/cost controls remain thin | speed MVP-A | second provider need or provider cost controls | Tech-lead |
| TD-004 | Client Surfaces | web mirror and several CE-kit journeys remain placeholders or deferred slices | MVP-A1 intentionally proves the backend without UI | MVP-A2 release gate (ANY-225) | Client Surfaces |
| TD-009 | Browser smoke validation | dev/prod kernel Compose smoke is real; browser/extension journeys still lack executable smoke evidence | browser proof belongs to MVP-A2 and product E2E children | ANY-224/ANY-225 and the first product CE E2E | Client Surfaces |
| TD-010 | Atom proof coverage | only the first strict atoms and a one-action kernel smoke are implemented; aggregate 11/11 and 3/3 evidence does not yet exist | contracts and proof are delivered in explicit A20/A21 slices | MVP-A1 gate (ANY-5) | Platform Core |
