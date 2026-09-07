# Freelancer Suite Bundle

MVP-B `ProductBundle`. Composed only by `apps/platform-api`'s composition root
(`bootstrap.py`); never imported by Platform Core or Platform Actions.

When enabled, it registers configs through platform-sdk's `ProductBundle` contract and must not
require changes to platform-core.

## Product config roots

As of ANY-32 (B01), `FreelancerSuiteBundle.config_roots()` returns `[]`: this package owns no
implemented product directories yet. The Freelancer Suite roadmap adds one product per
bundle-and-workflow issue, in this order:

1. ProposalAI (ANY-227)
2. Client Update Writer (ANY-413)
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
