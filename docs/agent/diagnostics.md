# Diagnostics and Safe Context Collection

The platform API and worker configure newline-delimited JSON logs on their existing runtime paths.
Records include a service, level, event name, safe message, and correlation identifiers when the
runtime already has them.

Sensitive fields are replaced before serialization. This includes credentials, authorization
headers, cookies, tokens, emails, prompts, user input, handoff tokens, and raw provider output.
Do not bypass the shared formatter with raw request or provider payloads.

To collect context after a failure:

    python scripts/agent/runner.py collect-context --failure-file path/to/output.txt

The command writes JSON under .agent/context/, which is ignored by Git. It captures sanitized tool
versions, Git status/diff summary, active plans, worktree endpoints and Compose status, and recent
API/worker logs. Individual diagnostic commands are best-effort; an unavailable Docker daemon does
not prevent the rest of the bundle from being written.

Inspect the bundle before sharing it outside the development environment. Collection is a safety
aid, not a substitute for review.
