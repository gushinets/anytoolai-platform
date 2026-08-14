# Tech Debt Tracker

| ID | Area | Debt | Why accepted | Expiry trigger | Owner |
|---|---|---|---|---|---|
| TD-002 | Artifacts | JSON/text in DB first | no media/files in MVP-A | artifact >1MB or file input | Backend |
| TD-003 | Provider | LiteLLM/fake-provider path first; retry ownership and the physical-call hard limit are enforced, but broader provider/cost controls remain thin | speed MVP-A | second provider need or provider cost controls | Tech-lead |
| TD-004 | Client Surfaces | A15a-c are delivered, but the web mirror and handoff, email-capture, and client-event CE helpers remain deferred slices | MVP-A1 intentionally proves the backend without UI | MVP-A2 release gate (ANY-225) | Client Surfaces |
| TD-009 | Browser smoke validation | dev/prod kernel Compose smoke is real; browser/extension journeys still lack executable smoke evidence | browser proof belongs to MVP-A2 and product E2E children | ANY-224/ANY-225 and the first product CE E2E | Client Surfaces |
| TD-010 | Atom proof coverage | all 11 types are registered and seven strict standalone runtime paths are configured; four strict atom slices and aggregate 11/11 and 3/3 evidence do not yet exist | contracts and proof are delivered in explicit A20/A21 slices | MVP-A1 gate (ANY-5) | Platform Core |
| TD-011 | Windows frontend validation | CE-kit API-type generation launches an extensionless pnpm shim that fails under Windows Node 24; frontend CI currently runs only on Ubuntu and no supported Node major is pinned | current Ubuntu required check remains green while the portable launch fix is isolated | `ce-kit-openapi-typescript-windows-launch.md` | Client Surfaces / DevEx |
| TD-012 | Architecture scan hygiene | the extension prompt-boundary test scans ignored dependency/build trees, so quick-check can fail after a frontend install even when tracked extension source is unchanged | clean CI workspaces run quick-check before installing frontend dependencies | `extension-boundary-generated-tree-exclusions.md` | DevEx |
