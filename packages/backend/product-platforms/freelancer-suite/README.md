# Freelancer Suite Bundle

MVP-B `ProductBundle`. Composed by the platform's three composition boundaries —
`apps/platform-api/bootstrap.py`, `apps/platform-worker/composition.py`, and
`scripts/agent/validate_configs.py` — with the identical default bundle set (enforced by
`ATAI008` and `tests/architecture/test_bundle_composition_parity.py`); never imported by Platform
Core or Platform Actions.

When enabled, it registers configs through platform-sdk's `ProductBundle` contract and must not
require changes to platform-core.

## Product config roots

As of ANY-413, `FreelancerSuiteBundle.config_roots()` returns one implemented product root:
`client_update_writer`. The Freelancer Suite roadmap adds one product per bundle-and-workflow
issue, in this order:

1. ProposalAI (ANY-227)
2. Client Update Writer (ANY-413) -- implemented
3. Brief Decoder (ANY-232)
4. Acceptance Builder (ANY-228)
5. Task Finder (ANY-231)
6. Send-Ready (ANY-230)

A product only appears in `config_roots()` once its own issue lands a real product directory
(product config, scenarios, workflows, action configs, prompts, strict schemas, and any handoff
map it needs) under `src/anytoolai_freelancer_suite/products/<name>/`. Additional atom-ready
products (Case Study, Scope Guard, Persuasion Lens, and others) remain capability backlog until an
issue schedules them -- they are not placeholder directories here.

Product meaning stays in this package, not in Platform Core.
