# Freelancer Suite Bundle

MVP-B `ProductBundle`. Composed by the platform's three composition boundaries —
`apps/platform-api/bootstrap.py`, `apps/platform-worker/composition.py`, and
`scripts/agent/validate_configs.py` — with the identical default bundle set (enforced by
`ATAI008` and `tests/architecture/test_bundle_composition_parity.py`); never imported by Platform
Core or Platform Actions.

When enabled, it registers configs through platform-sdk's `ProductBundle` contract and must not
require changes to platform-core.

## Product config roots

As of ANY-228, `FreelancerSuiteBundle.config_roots()` returns four implemented product roots, in
this order: `proposal_ai` (ANY-227), `client_update_writer` (ANY-413), `brief_decoder` (ANY-232)
and `acceptance_builder` (ANY-228).

Per `docs/product-specs/mvp-scope-source-of-truth.md`'s five-product committed release order
(`ANY-452`):

1. ProposalAI (ANY-227) -- implemented
2. Client Message Decoder
3. Scope Creep Guard
4. Send-Ready
5. Brief Decoder (ANY-232) -- implemented

Client Update Writer (ANY-413) and Acceptance Builder (ANY-228) are implemented as real product
directories -- those tickets landed them independently of the five-product sequence above -- but
are not themselves part of that committed release order: `mvp-scope-source-of-truth.md` places
them, along with External Task Finder & Fit, in the capability backlog without a committed
release order.

A product only appears in `config_roots()` once its own issue lands a real product directory
(product config, scenarios, workflows, action configs, prompts, strict schemas, and any handoff
map it needs) under `src/anytoolai_freelancer_suite/products/<name>/`.

Product meaning stays in this package, not in Platform Core.
