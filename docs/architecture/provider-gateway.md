# Provider Gateway

All model/provider calls go through Provider Gateway.

Provider Gateway responsibilities:

- provider policy resolution;
- timeout;
- retries;
- fallback policy when configured;
- structured output mode;
- provider call logging;
- token/cost metadata;
- latency metadata;
- user-safe provider errors.

Minimum provider policy fields:

```text
provider
model
temperature
timeout_seconds
max_retries
fallback_policy optional
structured_output_mode
```

Even before billing, provider calls must log:

- provider;
- model;
- input tokens;
- output tokens;
- latency in milliseconds;
- estimated cost;
- success/failure.

Direct provider SDK imports outside `platform-core/providers/adapters` are forbidden.
