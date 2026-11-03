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

## Review follow-up — round 2, 2026-11-03

- Added daemon-free Docker Compose CLI regression tests in
  `tests/compose/test_postgres_ports.py` for the resolved base+dev default and port override,
  standalone agent, base+prod (no publication), and base+Atom Lab default/override.
  Each published case requires exactly one TCP mapping with loopback host IP and the
  expected host/target ports. Ambient operator settings and .env files are excluded.
- Two negative cases resolve an added dev overlay with a wildcard publication and
  verify that the same security assertion rejects the resulting merged configuration.
- Wired these tests into the required compose-smoke-prod job before stack startup.
  Docker-free baseline retains the existing raw-YAML checks; missing Compose or failed
  config resolution fails the dedicated check instead of silently skipping it.
- Validation: 10 focused tests passed, covering eight resolved-Compose cases and two
  original YAML cases. Doctor and documentation validation passed. No live containers
  or provider calls are needed for this test-only change.
- Final targeted run including runner Compose-file wiring: 11 passed; Ruff and
  git diff --check passed. Corrected the moved execution-plan link in PR #232.

## SonarCloud follow-up — 2026-11-03

- Plan: add frozen dependency resolution and disable builds for the new Compose-test
  command, then run that exact CI command and documentation checks.
- SonarCloud on e1bb44dd reported githubactions:S8541 and githubactions:S8544 on the
  newly added uv run step. Added --frozen and --no-build; dependencies are already
  installed by the preceding uv sync --frozen --group dev step. No rule suppression,
  dependency or unrelated workflow changes.
- Exact CI command uv run --frozen --no-build python -m pytest
  tests/compose/test_postgres_ports.py passed: 8 tests. Doctor, validate-docs and
  git diff --check passed. Remote SonarCloud reanalysis requires a pushed commit;
  no passing remote quality gate is claimed for this local fix.
