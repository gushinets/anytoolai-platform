# Fake provider outputs

The fake provider selects fixtures by request metadata, never by prompt text.

Lookup order:

1. explicit `fixture_key` on the provider request
2. `request.metadata["fixture_key"]`
3. `action_config_id`
4. `request.metadata["action_config_id"]`

Each fixture file lives next to this README and is named `<fixture_key>.json`.

Supported fixture fields:

- `output_text`: literal provider output text
- `response_json`: JSON payload that will be serialized to text
- `input_tokens`
- `output_tokens`
- `latency_ms`
- `estimated_cost`
- `metadata`
