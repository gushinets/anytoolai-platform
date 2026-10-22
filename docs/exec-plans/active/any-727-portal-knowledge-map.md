# Execution Plan: ANY-727 Portal knowledge map

## Status

- State: active
- Owner: agent
- Created: 2026-10-23
- Last updated: 2026-10-23
- Review date: 2026-10-23
- Next action: finish canonical checks and sequential independent review; open the linked PR
- Blocker: none

## Goal and scope

[ANY-727](https://linear.app/paveldik/issue/ANY-727) implements the approved
2026-10-23 cross-repository audit with companion
[ANY-728](https://linear.app/paveldik/issue/ANY-728).
Add `docs/integrations/payment-portal.md`; link it from `AGENTS.md`,
`ARCHITECTURE.md`, and `docs/index.md`; add PR Peer impact; extend
`scripts/agent/validate_docs.py` and `tests/test_validate_docs.py`.

Observed baselines: Platform `79a2ada5b790f959a40b3e08451ef9ed8d97da5b`,
Portal `79dc3f4d204aec4ac9552e3d1da3481553cc8aef`.
The map delegates normative semantics to existing owners. No runtime, DB,
configuration, wire fixtures, generated artifacts or Region Resolver changes.

## Implementation and validation

- [x] Add a negative DOC002 test for a missing integration index entry while its file exists; observe failure before adding the required entry.
- [x] Write the map and root navigation; add the required entry and PR Peer impact.
- [ ] Run focused docs tests, validate-docs and supported canonical checks; record results and limitations.
- [ ] Commit; obtain fresh Astra xhigh then fresh Sol max review of identical base/head SHAs. Restart the cycle after fixes.
- [ ] Open the PR linked to ANY-728 and its companion PR; leave merge to a human.

## Review focus

- Request directions and actual versus target producer/consumer status.
- Guest identity/quota versus authenticated Portal identity and paid allowances.
- `anytoolai/default` versus `anytoolai/ru`; provisional production refusal.
- Historical provenance versus real conformance; no circular SHA maintenance.
- Required index entry enforced without adding network or runtime dependencies.

## Evidence

- Initial repository doctor: passed on Windows, Python 3.12.10, Node 24.18.0.
- The new missing-index test failed before the required entry was added; all four docs tests now pass.
- `python scripts/agent/runner.py validate-docs`: passed.
- Canonical `quick-check` is running. Final check results and sequential reviews
  will be recorded on the linked PR against its immutable commit SHA, so review
  evidence does not require changing the reviewed commit.
