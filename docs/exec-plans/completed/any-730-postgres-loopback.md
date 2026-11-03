# ANY-730: Local PostgreSQL publication

## Status

- Created: 2026-11-03
- State: completed
- Owner: agent
- Last updated: 2026-11-03
- Review date: 2026-11-10
- Next action: none for implementation; pending CI checks remain merge gates.
- Blocker: none for implementation; local validation limits are retained below.
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

## Review follow-up and completion — 2026-11-03

- Updated deployment and worktree instructions to require Docker Engine >=28.0.0
  for loopback remote isolation under default bridge networking. Older Linux Engines
  require an upgrade or adequate host firewall rules; shared-network deployments need
  a second-host check on the same L2 segment. Doctor does not enforce daemon version.
- Source: https://docs.docker.com/engine/network/port-publishing/ and
  [PR review finding](https://github.com/gushinets/anytoolai-platform/pull/232#discussion_r4452388630).
- CI on reviewed head 1241d990: full-check, baseline (ubuntu-latest), atoms-proof,
  postgresql-quota-concurrency, compose-smoke-dev and compose-smoke-prod passed.
  [Backend run](https://github.com/gushinets/anytoolai-platform/actions/runs/41602926107).
  Windows baseline and CodeRabbit were still pending at this follow-up; no all-green
  claim is made. Historical local baseline limitations above remain accurate.
- Implementation completed at the user's request; moved this plan to completed.
