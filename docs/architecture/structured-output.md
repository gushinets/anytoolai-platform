# Structured Output

Actions validate input and output at the boundary.

MVP-A must support:

- input schema validation;
- output schema validation;
- retry on invalid JSON;
- raw provider output artifact;
- normalized final output artifact;
- standardized validation errors.

No YOLO JSON probing.

## Library ownership

Structured-output semantics are owned by the structured action executor, not by Provider Gateway.

MVP-A uses PydanticAI inside `StructuredLlmActionExecutor` for:

- typed output binding;
- output validators;
- validation retry/reflection;
- structured-output mode selection where supported.

Provider Gateway uses LiteLLM SDK for provider/model access. LiteLLM must not independently enforce a second conflicting JSON schema for the same action.

Allowed pass-through:

```text
PydanticAI chooses provider-native/tool/prompted structured-output transport
  -> ProviderGateway passes the resulting request shape through LiteLLM SDK
```

Forbidden:

```text
StructuredLlmActionExecutor configures one schema
ProviderGateway independently configures another LiteLLM response_format/schema
```

That creates ambiguous failures and retry loops where the wrong layer owns the error.

## Validation retry vs transport retry

Validation retries belong to PydanticAI.

Transport retries belong to AnytoolAI ProviderGateway around LiteLLM SDK calls.

Each validation retry may produce another physical ProviderGateway attempt. The ProviderGateway hard cap must stop unbounded multiplication before a new provider call is made.

## Final validation and artifacts

AnytoolAI still final-validates output before downstream use.

For every structured LLM action, preserve:

- raw provider output artifact for debugging;
- normalized final output artifact for workflow mapping and frontend rendering;
- standardized safe validation error when output cannot be normalized.

PydanticAI usage summaries can help action-run metadata, but final contract validation and artifact persistence are platform responsibilities.
