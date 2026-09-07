# Execution Plan: ANY-32 B01 Freelancer Product Template And Bundle Loader

## Status

- State: active
- Owner: agent
- Created: 2026-09-07
- Last updated: 2026-09-07
- Review date: 2026-09-07
- Next action: none — implementation landed; awaiting code review.
- Blocker: none

## Goal

Define the standard for adding Freelancer product bundles without changing product-neutral
execution contracts: a real `ProductBundle` composition path from `apps/platform-api`'s bootstrap
through platform-core's `ConfigLoader`, proven by a test-only fixture bundle, with
`FreelancerSuiteBundle` reset to zero implemented product roots (the old eight-placeholder
scaffold removed).

## Scope

### In scope (implemented)

1. **`ProductBundle` contract** (`packages/backend/platform-sdk/src/anytoolai_platform_sdk/bundle.py`):
   `config_roots(self) -> list[Path]` (was `list[str]`), plus a `_package_dir()` helper
   (`Path(inspect.getfile(type(self))).resolve().parent`) subclasses use to resolve their product
   directories relative to their own installed package, independent of the caller's CWD. New test:
   `packages/backend/platform-sdk/tests/test_bundle.py`.
2. **`ConfigLoader` multi-root extension** (`packages/backend/platform-core/.../config/loader.py`):
   `ConfigLoader.__init__` gains `extra_product_roots: Sequence[Path] = ()`. `_load_products` loads
   `config_root/"products"` first (unchanged), then loads each `extra_product_roots` entry through
   the same `_load_product` pass — duplicate-id/missing-root/invalid-cross-reference handling is
   the existing single-pass validation, unchanged. Fully `Path`-only and `ProductBundle`-ignorant;
   platform-core never imports a bundle type. `build_config_registry`
   (`bootstrap/registry.py`) forwards `extra_product_roots` through to `ConfigLoader`.
3. **Composition root** (`apps/platform-api/src/anytoolai_platform_api/bootstrap.py`):
   `build_runtime` gains `bundles: Sequence[ProductBundle] | None = None`, defaulting in
   production to `[FreelancerSuiteBundle()]`. Flattens `bundle.config_roots()` across bundles, in
   the order given, into `extra_product_roots`. `loaded_bundles` now reports
   `["platform_actions", "kernel_demo", *(b.bundle_id for b in bundles)]` — the bundles actually
   composed, not a fabricated literal. This is the only module allowed to import
   `anytoolai_freelancer_suite` (see boundary proof, item 6).
4. **`FreelancerSuiteBundle` cleanup**
   (`packages/backend/product-platforms/freelancer-suite/`): `config_roots()` returns `[]`; the
   eight placeholder `products/<name>/` directories (each only a `README.md`, no real config) are
   deleted. `tests/test_bundle_loads.py` and `README.md` rewritten to describe the 6-product
   roadmap (ProposalAI, Client Update Writer, Brief Decoder, Acceptance Builder, Task Finder,
   Send-Ready), zero implemented today.
5. **Test-only fixture bundle and loader evidence**
   (`apps/platform-api/tests/fixtures/fixture_product/` and `fixture_product_duplicate/` — a
   byte-identical copy, used only for the duplicate-id case; `apps/platform-api/tests/test_bundle_composition.py`):
   `FixtureProductBundle` (defined in the test module, not exported) covers, all through the real
   `bootstrap.build_runtime`: happy path into the shared registry; production default
   (`build_runtime()`, no override) excludes the fixture bundle from `loaded_bundles` and the
   registry; CWD-independent resolution (`monkeypatch.chdir(tmp_path)`); a missing root raising
   `RegistryLoadError`; duplicate `product_id` across two bundles failing identically in both
   orderings (parametrized); an invalid cross-reference (a `tmp_path` copy of the fixture with a
   mutated `workflow_id`) failing via the existing `BrokenReferenceError` path.
6. **Architecture proof for the new path**
   (`scripts/agent/validate_architecture.py`'s new `check_freelancer_suite_import_boundary`,
   wired into `main()` as `ATAI008`; `tests/architecture/test_freelancer_suite_import_boundary.py`):
   asserts `anytoolai_freelancer_suite` is imported only from
   `apps/platform-api/src/anytoolai_platform_api/bootstrap.py` across `apps/` and `packages/`
   (the package's own source/tests excluded), plus a text-level check that
   `config/loader.py`/`bootstrap/registry.py` carry no `anytoolai_freelancer`/`FreelancerSuiteBundle`
   token. Regression fixtures prove the AST-based detection itself (a `tmp_path` package with an
   offending import) rather than only asserting today's real-repo state is clean.
7. **Docs**: `docs/product-specs/add-product-recipe.md` and `docs/product-specs/mvp-b-handoff-note.md`
   rewritten to drop the "eight-product working example" framing and describe the new
   `_package_dir()`-resolved, `ConfigLoader.extra_product_roots`-loaded contract. `README.md`'s
   MVP-B line also updated (found via the required repo-wide grep for stale "eight"/
   `FreelancerSuiteBundle` references) — it still said "eight thin ... CE-first products", already
   superseded by `docs/exec-plans/completed/web-first-product-plan-alignment.md`'s six-product
   web-first realignment.

### Dependency wiring (not in the original 7-step list, required to make it work)

`apps/platform-api/bootstrap.py` now imports `anytoolai_freelancer_suite` and
`anytoolai_platform_sdk` directly, so:

- `apps/platform-api/pyproject.toml` gained `anytoolai-platform-sdk` and
  `anytoolai-freelancer-suite` as direct dependencies, with matching `[tool.uv.sources]` path
  entries; `apps/platform-api/uv.lock` regenerated (`uv lock --project apps/platform-api`).
- `scripts/agent/quick_check.py`'s `EDITABLE_PROJECTS` gained the freelancer-suite package
  (installed before `apps/platform-api`'s own editable install). Without this, `quick-check`'s own
  `apps/platform-api/tests` run would fail on `ModuleNotFoundError: anytoolai_freelancer_suite`
  when importing `bootstrap.py` — `full-check`'s pre-existing freelancer-suite install step runs
  only *after* `quick-check`'s pytest pass, too late for this. `full-check`'s own
  freelancer-suite install/test step was left as-is (now redundant but harmless) since it still
  owns running `packages/backend/product-platforms/freelancer-suite/tests`, which `quick-check`'s
  `PYTEST_TARGETS` does not include.

### Out of scope (per issue non-goals and plan)

Real product behavior/content for any of the 6 named products (ANY-227 and siblings),
`apps/web-mirror` `WebProductDefinition`/page/renderer changes, a generic frontend/plugin
framework, a product-event/metric registry (ANY-17), product-specific backend endpoints, runtime
editing UI, dedicated Chrome Extensions.

### Known follow-up: `apps/platform-worker` does not compose `ProductBundle`s

`apps/platform-worker/src/anytoolai_platform_worker/composition.py`'s `build_worker()` calls
`build_config_registry(config_root)` with no `extra_product_roots` and never imports
`FreelancerSuiteBundle`/`ProductBundle` — only `apps/platform-api/bootstrap.py` does. Today this is
harmless: `FreelancerSuiteBundle.config_roots()` is `[]`, so platform-api's registry and
platform-worker's registry are identical in production regardless. It stops being harmless the
moment a real product bundle (starting with ProposalAI in ANY-227) contributes a non-empty
`config_roots()` — platform-api would then validate and accept scenario starts referencing that
product's workflows while platform-worker's own registry lacks them, so a claimed job fails at
execution time on a missing workflow/action lookup even though the API layer accepted it.

Deliberately not wired in this ticket (flagged in code review cycle 1, addressed here rather than
in code): doing so is more than a mechanical copy of `bootstrap.py`'s pattern — it also requires an
architecture decision this ticket's contract doesn't currently make, namely which composition roots
are allowed to import a product-platforms package. `scripts/agent/validate_architecture.py`'s
`check_freelancer_suite_import_boundary` (ATAI008) currently asserts exactly one allowed importer
(`apps/platform-api/src/anytoolai_platform_api/bootstrap.py`); adding platform-worker as a second
importer means updating that boundary check (and its test fixtures) at the same time as the worker
wiring, which is a broader change than "fix what B01 shipped." Tracked as a required prerequisite
for ANY-227 (the first ticket that gives `FreelancerSuiteBundle.config_roots()` real content): that
ticket (or a dedicated follow-up filed alongside it) must either wire `build_worker()` to accept
`bundles` the same way `build_runtime()` does, or explicitly justify why platform-api and
platform-worker are allowed to see different product registries.

## Verification

```
python scripts/agent/runner.py validate-configs   # pass
python scripts/agent/runner.py validate-architecture  # pass
python scripts/agent/runner.py quick-check        # pass (1190 passed)
python scripts/agent/runner.py full-check         # see Progress log
```

## Decision log

- Removed the 8 placeholder `products/<name>/` directories rather than leaving them as empty
  scaffolding (plan risk #2) — the issue requires registering only implemented roots, and 3 of the
  8 old names (`case_study`, `scope_guard`, `persuasion_lens`) aren't even in the 6-product target
  set; keeping empty dirs for names outside that set would itself be a stale claim.
- The fixture-bundle duplicate-id test reuses a byte-identical copy of `fixture_product` (rather
  than hand-writing a second, differently-shaped fixture) because `ConfigLoader._load_product`
  checks `product_id` duplication before loading any of a product's own
  action_configs/workflows/scenarios files — whichever bundle is processed second in either
  ordering never reaches those files, so identical internal ids are safe.
- `FixtureProductBundle` lives inside `test_bundle_composition.py` itself, not as a separate
  `apps/platform-api/tests/fixtures/__init__.py` package, to avoid a generic top-level module name
  ("fixtures") colliding with any other rootless test directory across the combined quick-check
  pytest run.

## Progress log

- 2026-09-07: Implementation complete (steps 1-7 above). All four required verification commands
  green locally: `validate-configs`, `validate-architecture`, `quick-check` (1190 passed), and
  `full-check` (quick-check's 1190 + frontend typecheck/test/build across 7 workspace projects +
  `packages/backend/product-platforms/freelancer-suite/tests`, 2 passed) — exit code 0 end to end.
