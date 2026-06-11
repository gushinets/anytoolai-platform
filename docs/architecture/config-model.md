# Config Model

In MVP-A definitions live in YAML/Markdown and runtime state lives in PostgreSQL.

Definitions:

- product
- frontend
- scenario
- workflow
- action definition
- action configuration
- prompt
- provider policy
- quota policy
- handoff definition

Source of truth in MVP-A:

```text
Product / Scenario / Workflow / Action Config / Prompt = repo config.
Runtime state / Events / Artifacts / Sessions = database.
```

Prompt registry entries live in repo Markdown/config and must expose:

- `prompt_ref`
- version
- template
- input variables
- `output_schema_ref`

Frontend must not see system prompts or choose prompt versions.

Config validation must run in CI and before runtime startup. Broken references must fail startup.
