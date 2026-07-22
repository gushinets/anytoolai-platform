# Platform Migrations

MVP-A runtime tables:

- scenario_sessions
- jobs
- action_runs
- provider_calls
- artifacts
- event_log
- guest_identities
- guest_quota_usage
- email_captures
- paywall_intents
- product_handoffs

Migration `0003` currently implements the A13 guest identity and guest quota usage tables.
Email capture and paywall intent remain separate access-lite slices.
