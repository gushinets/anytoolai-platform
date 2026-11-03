# ANY-730: Local PostgreSQL publication

## Status

- Created: 2026-11-03
- State: active
- Owner: agent
- Last updated: 2026-11-03
- Review date: 2026-11-10
- Next action: owner review; rerun full baseline in a working test environment.
- Blocker: full baseline did not complete; see validation limits below.
- Goal: restrict dev/agent PostgreSQL host publication to IPv4 loopback.

## Implementation plan

1. Bind base and agent PostgreSQL publications to 127.0.0.1; retain port overrides.
2. Add a focused Python architecture regression test and clarify local connection docs.
3. Validate resolved dev/default/override, agent, production and Atom Lab configurations;
   run runner worktree tests and quick-check.
4. Check live SQL/API/worker connectivity if Docker is available; record verification limits.

## Boundaries

No internal DSN, credentials, firewall, schema or runtime logic changes.
Relevant contracts: docs/agent/worktree-runtime.md and infra/deployment/README.md.

## Validation

- Doctor passed with managed Python 3.12.13; system Python lacks pytest/pydantic.
- Existing unrelated ANY-629 execution-plan edit is preserved.
- Resolved Docker Compose v5.3.1 JSON verified: dev default 5432, two project/port
  overrides 15555 and 15556, agent 55432: exactly one PostgreSQL binding, host_ip
  127.0.0.1 and target 5432. Base+prod has no PostgreSQL ports; base+Atom Lab
  retains exactly one loopback binding on 5432.
- Isolated live PostgreSQL 18 checks passed for base (override 25573) and agent
  (55432): host psycopg SELECT 1, SELECT 1 from a separate container over the
  Compose network using postgres:5432, inspect HostIp 127.0.0.1, and refused TCP
  connection through host network IP 192.168.239.134. Test projects were removed.
  Agent has no healthcheck; host TCP readiness was awaited during initialization.
- Focused regression/runner tests: 6 passed (loopback, worktree identity/scoping,
  explicit port overrides and worktree smoke command wiring).
- Documentation validation and git diff --check passed.
- No external second-host network audit or full API-to-worker live smoke was run;
  separate-container SQL proves internal database reachability, not the full job journey.
- Pre-existing unrelated local-skill wording exists in other tracked execution plans;
  no such wording was introduced or unrelated files changed by this ticket.
- A separate architecture-suite diagnostic could not collect because installed LiteLLM
  raised ImportError for LoggerContext from its partially initialized rust_bridge.catalog;
  no provider/runtime dependency changes are included in this configuration fix.

- Full quick-check: config, architecture, docs validation and generated-doc drift passed;
  pytest reported two failures before stalling near 33%. After several minutes without
  progress it was stopped (SIGINT did not complete; SIGTERM ended the process). No
  final failure traceback was produced, so causes of those two failures are unverified.
  This is not a passing full baseline. Focused tests passed independently.
