# Proposal AI VPS Live Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy Proposal AI on the existing VPS stack with OpenAI calls routed from `platform-worker` through Squid, an initially unmetered guest mode that can later restore the canonical anonymous quota, and reusable local/live deployment machinery for later Freelancer Suite products.

**Architecture:** Keep checked-in product YAML canonical and fake-backed. An explicit command in the existing Freelancer Suite composition boundary copies the whole product tree to a gitignored deployment profile, strictly transforms only enabled products, validates it with `ConfigLoader`, and emits a cross-platform manifest. Runner composes that profile into API and worker through one live overlay, while API and web apply the same released-product allowlist and production remains fail-closed.

**Tech Stack:** Python 3.12, `argparse`, `pathlib`, PyYAML, FastAPI/Pydantic, Docker Compose, Next.js 15/React 19/TypeScript, Vitest, pytest, PostgreSQL, LiteLLM/OpenAI, Squid.

**Spec:** `docs/superpowers/specs/2026-09-25-proposal-ai-vps-live-deployment-design.md`

## Status

- State: active
- Owner: agent
- Created: 2026-09-25
- Last updated: 2026-09-25
- Review date: 2026-10-02
- Next action: choose execution mode, then start Task 1 with a clean implementation worktree.
- Blocker: none; the design was externally reviewed and approved for implementation.

## Scope

### In scope

- Generated live product profiles, local live runner commands, API/web release allowlists, unmetered frontend behavior, production web/Compose wiring, Squid routing, readiness verification, runbooks, and repository/acceptance checks.

### Out of scope

- Repository-owned ingress/proxy/firewall automation, new provider abstractions, arbitrary YAML patching, billing/authentication, and speculative per-action live mappings.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/frontend-boundaries.md`
- `docs/architecture/quota-model.md`
- `docs/product-specs/add-product-recipe.md`
- `docs/superpowers/specs/2026-09-25-proposal-ai-vps-live-deployment-design.md`

## Contracts touched

- API: released-product admission on runtime-config, quota, and scenario-start routes.
- DB: no schema change; existing quota usage rows retain current semantics.
- Config: generated runtime copy of Freelancer Suite product YAML, with canonical files unchanged.
- Provider: enabled product actions use `default_text_generation_v1`; Provider Gateway/LiteLLM remain authoritative.
- Frontend: build-time product allowlist and `quotaSummary: null` behavior.
- Deployment: new live Compose overlay, web image/service, production preflight, and Squid environment.

## Global Constraints

- Canonical product YAML remains the only committed product definition; generated profiles live only under `.agent/deployment-profiles/`.
- Normal `dev-up`, `validate-configs`, quick/full checks, and credential-free smokes remain canonical and fake-backed.
- Provider/model choice stays out of product code and frontend code; live calls continue through Provider Gateway and the existing LiteLLM adapter.
- Only `platform-worker` receives `OPENAI_API_KEY`, `HTTPS_PROXY`, `AIOHTTP_TRUST_ENV`, and optional Squid CA configuration.
- `ANYTOOLAI_UNMETERED_PRODUCT_IDS` is required in production but may be explicitly empty; missing and empty must remain distinguishable.
- `ANYTOOLAI_ENABLED_PRODUCT_IDS` is optional in development and required non-empty in production and the production web build.
- No database migration, generic YAML overlay engine, LiteLLM Proxy, new provider abstraction, or provider/model API exposure.
- API and worker must validate the same mounted profile before runner reports readiness.
- Profile fingerprints are SHA-256 over sorted relative POSIX paths and exact file bytes, with length prefixes and no absolute paths or metadata.
- Production API and web ports bind to `127.0.0.1`; PostgreSQL is not published.
- Existing untracked `.cursor/` and `docs/exec-plans/active/atoms-proof-required-ci-gate.md` are unrelated and must not be staged or changed.

## Review Focus

- Missing versus explicitly empty `ANYTOOLAI_UNMETERED_PRODUCT_IDS`: missing fails preflight; empty prints every enabled product as `canonical` and proceeds.
- Disabled products retaining `default_fake_provider_v1`: they remain valid in the copied tree and never fail effective-config readiness.
- Windows host versus Linux container fingerprints: identical relative paths and bytes produce the same digest despite path separators.
- API/web allowlist drift: missing production build input fails; disabled products disappear from web and all three product-entry API routes return the safe not-found response.
- Proxy/secret isolation: live worker receives the OpenAI key and Squid settings; API/web and ordinary `dev-up` receive none of them.

## File Map

### Create

- `tests/test_validate_configs.py` — deployment-profile generation, fingerprint, transform, manifest, and read-only checker tests.
- `infra/compose/docker-compose.live.yml` — generated product-tree mounts and worker-only live provider/proxy environment.
- `infra/docker/web-mirror.Dockerfile` — production multi-stage Next.js image with a required baked allowlist.

### Modify

- `scripts/agent/validate_configs.py` — retain default canonical validation; add explicit build/check profile commands.
- `scripts/agent/runner.py` — deployment selectors, `dev-live-up`, `dev-web`, `prod-up`, `prod-fake-up`, live Compose selection, effective-config checks, and web readiness.
- `tests/test_runner.py` — CLI, environment precedence, commands, preflight, safe output, and readiness tests.
- `apps/platform-api/src/anytoolai_platform_api/settings.py` — optional released-product allowlist parsing.
- `apps/platform-api/src/anytoolai_platform_api/main.py` — load settings once and reject unknown allowlist ids at startup.
- `apps/platform-api/src/anytoolai_platform_api/dependencies.py` — settings lookup plus enabled-product admission dependency.
- `apps/platform-api/src/anytoolai_platform_api/routers/runtime_config.py` — enforce admission before runtime-config lookup.
- `apps/platform-api/src/anytoolai_platform_api/routers/identity_quota.py` — enforce admission before quota/storage work.
- `apps/platform-api/src/anytoolai_platform_api/routers/scenario_runtime.py` — enforce admission before scenario start/storage work.
- `apps/platform-api/tests/test_runtime_config.py` — startup and runtime-config allowlist coverage.
- `apps/platform-api/tests/test_identity_quota_api.py` — disabled-product quota rejection.
- `apps/platform-api/tests/test_scenario_runtime_api.py` — disabled-product start rejection without side effects.
- `apps/web-mirror/src/products/registry.ts` — build-time allowlist sets `enabled` without narrowing the complete registry.
- `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` — skip initial and repeat quota reads for `quotaSummary: null`.
- `apps/web-mirror/test/fixtures/platformResponses.ts` — explicit metered runtime fixture default.
- `apps/web-mirror/test/registry.test.tsx` — absent/present build-time allowlist behavior and complete listing.
- `apps/web-mirror/test/HomePage.test.tsx` — disabled product card suppression.
- `apps/web-mirror/test/ProductRunPage.test.tsx` — metered and unmetered initial/repeat flows.
- `infra/compose/docker-compose.prod.yml` — required allowlist/memory, web service, loopback bindings, and production safety overrides.
- `infra/compose/.env.example` — documented deployment controls with no secrets.
- `.dockerignore` — exclude `.agent/` so generated profiles/evidence are mounted at runtime, never copied into images.
- `.github/workflows/backend.yml` — keep the required production Compose smoke credential-free through explicit fake mode.
- `infra/deployment/README.md` — VPS, Squid, TLS, reverse proxy, quota switch, deploy, acceptance, and rollback runbook.
- `docs/product-specs/add-product-recipe.md` — reusable standard-fake live-transform contract.

---

### Task 1: Build and verify generated deployment profiles

**Files:**

- Modify: `scripts/agent/validate_configs.py`
- Create: `tests/test_validate_configs.py`
- Verify: `tests/architecture/test_bundle_composition_parity.py`

**Interfaces:**

- Produces: `build_deployment_profile(output_dir: Path, enabled_product_ids: Sequence[str], unmetered_product_ids: AbstractSet[str]) -> DeploymentProfileManifest`.
- Produces: `tree_fingerprint(root: Path) -> str`.
- Produces CLI: `build-deployment-profile --output-dir PATH --enabled-product ID [--unmetered-product ID]`.
- Produces CLI: `check-deployment-profile --products-root PATH --expected-fingerprint HEX --expect-product PRODUCT=PROVIDER,QUOTA_OR_DASH`.
- Preserves: no-argument `main()` and `python scripts/agent/runner.py validate-configs` load only canonical roots and write nothing.

- [ ] **Step 1: Add failing tests for canonical validation and deterministic fingerprints**

Add tests with these exact behaviors:

```python
def test_default_validation_does_not_create_a_deployment_profile(monkeypatch, tmp_path):
    module = load_validate_configs_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "load_registry", lambda: object())
    monkeypatch.setattr(module, "load_model_capability_overrides", lambda _path: object())
    assert module.main([]) == 0
    assert not (tmp_path / ".agent").exists()


def test_tree_fingerprint_uses_posix_relative_paths_and_exact_bytes(tmp_path):
    root = tmp_path / "products"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "a.yaml").write_bytes(b"x\r\ny\n")
    first = tree_fingerprint(root)
    assert normalized_relative_path(root, root / "nested" / "a.yaml") == "nested/a.yaml"
    assert first == "00bff2c995b88fa0e64c19d3f9d02105190c40d9f0921d54ea0e4c53f881a21e"
    assert tree_fingerprint(root) == first
    (root / "nested" / "a.yaml").write_bytes(b"x\ny\n")
    assert tree_fingerprint(root) != first
```

Also pin ordering by creating the same files in opposite creation order and asserting equal hashes. Compute each hash item as `len(path_bytes).to_bytes(8, "big") + path_bytes + len(file_bytes).to_bytes(8, "big") + file_bytes`.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run:

```powershell
python -m pytest tests/test_validate_configs.py -q
```

Expected: failures because the profile/fingerprint interfaces and argv-aware `main()` do not exist.

- [ ] **Step 3: Implement the minimal fingerprint and manifest types**

Keep them in `validate_configs.py`; do not create a framework module for one caller.

```python
LIVE_PROVIDER_POLICY_REF = "default_text_generation_v1"
FAKE_PROVIDER_POLICY_REF = "default_fake_provider_v1"
CONTAINER_PRODUCTS_ROOT = Path(
    "/app/packages/backend/product-platforms/freelancer-suite/src/"
    "anytoolai_freelancer_suite/products"
)


@dataclass(frozen=True)
class ProductProfileExpectation:
    provider_policy_ref: str
    quota_policy_ref: str | None


@dataclass(frozen=True)
class DeploymentProfileManifest:
    source_products_root: str
    generated_products_root: str
    container_products_root: str
    enabled_products: dict[str, ProductProfileExpectation]
    source_fingerprint: str
    profile_fingerprint: str


def normalized_relative_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def tree_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: normalized_relative_path(root, path),
    )
    for path in files:
        for part in (normalized_relative_path(root, path).encode(), path.read_bytes()):
            digest.update(len(part).to_bytes(8, "big"))
            digest.update(part)
    return digest.hexdigest()
```

Serialize the manifest with stable `json.dumps(..., sort_keys=True, indent=2)` to `manifest.json` beside `products/`.

- [ ] **Step 4: Add failing transform tests using a small real-shaped fixture tree**

Cover all of these cases in `tests/test_validate_configs.py`:

```python
def test_build_profile_transforms_only_enabled_product(...):
    manifest = build_deployment_profile(
        output_dir,
        enabled_product_ids=["proposal_ai"],
        unmetered_product_ids={"proposal_ai"},
    )
    assert generated_action_ref(output_dir, "proposal_ai") == LIVE_PROVIDER_POLICY_REF
    assert generated_quota_ref(output_dir, "proposal_ai") is None
    assert generated_quota_policies(output_dir, "proposal_ai") == []
    assert generated_action_ref(output_dir, "client_update_writer") == FAKE_PROVIDER_POLICY_REF
    assert manifest.enabled_products["proposal_ai"].quota_policy_ref is None


@pytest.mark.parametrize(
    ("enabled", "unmetered", "message"),
    [
        (["missing"], set(), "unknown product"),
        (["proposal_ai"], {"brief_decoder"}, "must be a subset"),
        (["already_live"], set(), "no action config uses default_fake_provider_v1"),
    ],
)
def test_build_profile_fails_closed(enabled, unmetered, message, ...):
    with pytest.raises(ValueError, match=message):
        build_deployment_profile(output_dir, enabled, unmetered)
```

Add one canonical-mode assertion that preserves `proposal_ai.guest_quota_v1` and the canonical `quotas.yaml` bytes, and one unmetered Client Update Writer assertion proving canonical no-quota remains valid.

- [ ] **Step 5: Implement strict copy-and-transform behavior**

Resolve `FreelancerSuiteBundle().config_roots()`, require their common parent to be the package `products/` directory, copy that complete directory, and only edit these generated files:

```python
def _transform_live_product(product_dir: Path, *, unmetered: bool) -> None:
    action_path = product_dir / "action_configs.yaml"
    payload = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    changed = 0
    for item in payload["action_configs"]:
        if item.get("provider_policy_ref") == FAKE_PROVIDER_POLICY_REF:
            item["provider_policy_ref"] = LIVE_PROVIDER_POLICY_REF
            changed += 1
    if changed == 0:
        raise ValueError(f"{product_dir.name}: no action config uses {FAKE_PROVIDER_POLICY_REF}")
    if any(item.get("provider_policy_ref") == FAKE_PROVIDER_POLICY_REF for item in payload["action_configs"]):
        raise ValueError(f"{product_dir.name}: fake provider policy remains after transform")
    action_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    if unmetered:
        product_path = product_dir / "product.yaml"
        product = yaml.safe_load(product_path.read_text(encoding="utf-8"))
        product.pop("quota_policy_ref", None)
        product_path.write_text(yaml.safe_dump(product, sort_keys=False), encoding="utf-8")
        (product_dir / "quotas.yaml").write_text("quota_policies: []\n", encoding="utf-8")
```

Build in a sibling temporary directory, load kernel plus generated product roots through the real `ConfigLoader`, validate expectations, then replace the old generated directory. A failed build must leave no half-written profile selected by Compose.

- [ ] **Step 6: Implement read-only effective-profile checking**

Derive action configurations by traversing the enabled product's scenarios and workflow steps, not by checking every product in the registry. The checker must assert:

```python
assert common_products_root(FreelancerSuiteBundle().config_roots()).resolve() == products_root.resolve()
assert tree_fingerprint(products_root) == expected_fingerprint
for product_id, expected in expectations.items():
    product = require_product(registry, product_id)
    assert product.quota_policy_ref == expected.quota_policy_ref
    for action_config_id in action_config_ids_for_product(registry, product_id):
        assert registry.action_configurations[action_config_id].provider_policy_ref == expected.provider_policy_ref
```

Do not inspect provider policies belonging only to disabled products. Parse `QUOTA_OR_DASH` as `None` only for the literal `-`.

- [ ] **Step 7: Add the explicit CLI without changing default validation**

Use optional `argparse` subcommands:

```text
validate_configs.py
validate_configs.py build-deployment-profile --output-dir ... --enabled-product proposal_ai --unmetered-product proposal_ai
validate_configs.py check-deployment-profile --products-root ... --expected-fingerprint ... --expect-product proposal_ai=default_text_generation_v1,-
```

The no-argument branch must call the existing `load_registry()` and catalog override validation only. Both new commands return nonzero with a concise stderr message on invalid ids, transforms, paths, fingerprints, or references.

- [ ] **Step 8: Run focused and architecture tests**

Run:

```powershell
python -m pytest tests/test_validate_configs.py tests/architecture/test_bundle_composition_parity.py tests/architecture/test_freelancer_suite_import_boundary.py -q
python scripts/agent/runner.py validate-configs
```

Expected: all pass; the second command creates no `.agent/deployment-profiles` directory.

- [ ] **Step 9: Commit Task 1**

```powershell
git add scripts/agent/validate_configs.py tests/test_validate_configs.py
git commit -m "feat: generate validated live product profiles"
```

---

### Task 2: Add reusable local live orchestration

**Files:**

- Create: `infra/compose/docker-compose.live.yml`
- Modify: `scripts/agent/runner.py`
- Modify: `tests/test_runner.py`

**Interfaces:**

- Consumes: Task 1 build/check CLIs and `manifest.json`.
- Produces: `dev-live-up --product ID [--quota-mode canonical|unmetered]`.
- Produces: `dev-web`.
- Produces: `_run_effective_profile_checks(compose_command, manifest) -> int` shared by local live and production.

- [ ] **Step 1: Add failing runner CLI and command-construction tests**

Add assertions for:

```python
def test_dev_live_up_defaults_to_unmetered(parse_args):
    args = parse_args(["dev-live-up", "--product", "proposal_ai"])
    assert args.product == "proposal_ai"
    assert args.quota_mode == "unmetered"


def test_dev_live_compose_uses_base_dev_and_live_overlays(...):
    command = _dev_live_compose_command(identity, "up", "-d")
    assert compose_files(command) == [COMPOSE_FILE, COMPOSE_OVERRIDE_FILE, COMPOSE_LIVE_FILE]


def test_normal_dev_compose_never_uses_live_overlay_or_live_env_file(...):
    command = _compose_command(identity, "up")
    assert str(COMPOSE_LIVE_FILE) not in command
    assert str(LIVE_ENV_FILE) not in command
```

Also assert `--product`/`--quota-mode` are rejected for commands other than `dev-live-up`.

- [ ] **Step 2: Run the new runner tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_runner.py -q
```

Expected: focused failures for missing live constants, CLI options, and commands.

- [ ] **Step 3: Add the live Compose overlay**

Create `infra/compose/docker-compose.live.yml` with one mount variable and worker-only secrets:

```yaml
services:
  platform-api:
    volumes:
      - type: bind
        source: ${ANYTOOLAI_DEPLOYMENT_PRODUCTS_ROOT:?generated products root is required}
        target: /app/packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products
        read_only: true
  platform-worker:
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY:?OPENAI_API_KEY is required for live mode}
      HTTPS_PROXY: ${ANYTOOLAI_LLM_HTTPS_PROXY-}
      AIOHTTP_TRUST_ENV: "true"
    volumes:
      - type: bind
        source: ${ANYTOOLAI_DEPLOYMENT_PRODUCTS_ROOT:?generated products root is required}
        target: /app/packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products
        read_only: true
```

Do not add proxy variables to `docker-compose.yml`. Document TLS-intercept CA as an operator-only extra bind override unless the real Squid configuration proves interception is enabled; do not add a second permanent overlay speculatively.

- [ ] **Step 4: Implement profile subprocess and identical container-check arguments**

Runner must call Task 1 as a subprocess, then read `manifest.json`:

```python
def _deployment_profile_dir(compose_project: str) -> Path:
    return ROOT / ".agent" / "deployment-profiles" / compose_project / "freelancer-suite"


def _profile_check_args(manifest: dict[str, object]) -> list[str]:
    args = [
        "scripts/agent/validate_configs.py",
        "check-deployment-profile",
        "--products-root",
        CONTAINER_PRODUCTS_ROOT,
        "--expected-fingerprint",
        manifest["profile_fingerprint"],
    ]
    for product_id, expectation in sorted(manifest["enabled_products"].items()):
        quota = expectation["quota_policy_ref"] or "-"
        args.extend(["--expect-product", f"{product_id}={expectation['provider_policy_ref']},{quota}"])
    return args
```

Use the same `_profile_check_args()` output for `platform-api` and `platform-worker`; only each container's `uv run --project ... --no-sync python` prefix differs. Any nonzero check aborts readiness.

- [ ] **Step 5: Implement `dev-live-up`**

The command must:

1. resolve `runtime_identity()`;
2. resolve `OPENAI_API_KEY` and optional `ANYTOOLAI_LLM_HTTPS_PROXY` from shell first, then optional `.env.live`, rejecting a missing/blank key before Compose;
3. invoke profile build with the requested product and quota mode;
4. set `ANYTOOLAI_DEPLOYMENT_PRODUCTS_ROOT` to the generated host directory;
5. run base + dev + live Compose;
6. wait for API health without printing “ready” yet;
7. execute both container checks;
8. print endpoints plus `provider=default_text_generation_v1` and the selected quota mode.

Keep environment-file parsing in a small runner helper supporting documented `KEY=value`, quoted values, blank values, comments, and exported shell precedence including empty strings. Never print resolved secret values.

- [ ] **Step 6: Implement `dev-web`**

Use the existing worktree identity and existing runner subprocess helper:

```python
def dev_web() -> int:
    identity = runtime_identity()
    env = runner_env()
    env["PLATFORM_API_BASE_URL"] = identity.api_url
    return run_with_env(["pnpm", "--filter", "@anytoolai/web-mirror", "dev"], env)
```

No process supervisor and no fixed port fallback are added.

- [ ] **Step 7: Add failure-path tests**

Pin these outcomes in `tests/test_runner.py`:

- absent or blank live key returns `2` before profile generation, while an absent local proxy leaves `HTTPS_PROXY` empty;
- profile generation failure never calls Compose;
- API check failure skips worker check and never prints “ready”;
- worker check failure never prints “ready”;
- disabled-product fake refs are not passed as expectations;
- `dev-down` after live mode still addresses the same Compose project;
- `dev-web` exports the derived worktree API URL.

- [ ] **Step 8: Run focused tests and render Compose**

Run:

```powershell
python -m pytest tests/test_runner.py tests/test_validate_configs.py -q
$env:OPENAI_API_KEY='test-only'
$env:ANYTOOLAI_LLM_HTTPS_PROXY='http://proxy.invalid:3128'
$env:ANYTOOLAI_DEPLOYMENT_PRODUCTS_ROOT=(Resolve-Path '.').Path
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.override.yml -f infra/compose/docker-compose.live.yml config --quiet
```

Expected: tests and Compose render pass. Remove the three temporary shell variables after the check.

- [ ] **Step 9: Commit Task 2**

```powershell
git add scripts/agent/runner.py tests/test_runner.py infra/compose/docker-compose.live.yml
git commit -m "feat: add reusable local live mode"
```

---

### Task 3: Enforce the released-product allowlist in Platform API

**Files:**

- Modify: `apps/platform-api/src/anytoolai_platform_api/settings.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/main.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/dependencies.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/routers/runtime_config.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/routers/identity_quota.py`
- Modify: `apps/platform-api/src/anytoolai_platform_api/routers/scenario_runtime.py`
- Modify: `apps/platform-api/tests/test_runtime_config.py`
- Modify: `apps/platform-api/tests/test_identity_quota_api.py`
- Modify: `apps/platform-api/tests/test_scenario_runtime_api.py`

**Interfaces:**

- Produces: `Settings.enabled_product_ids: frozenset[str] | None` (`None` means unrestricted development).
- Produces: `require_enabled_product(product_id, settings) -> str` FastAPI dependency.
- Preserves: the existing safe `404 product_not_found` response shape.

- [ ] **Step 1: Add failing settings/startup tests**

Test exact parsing and startup behavior:

```python
def test_enabled_products_absent_means_all(monkeypatch):
    monkeypatch.delenv("ANYTOOLAI_ENABLED_PRODUCT_IDS", raising=False)
    assert Settings.from_env().enabled_product_ids is None


def test_enabled_products_are_trimmed_and_deduplicated(monkeypatch):
    monkeypatch.setenv("ANYTOOLAI_ENABLED_PRODUCT_IDS", " proposal_ai,proposal_ai ")
    assert Settings.from_env().enabled_product_ids == frozenset({"proposal_ai"})


def test_unknown_enabled_product_fails_app_startup(monkeypatch):
    monkeypatch.setenv("ANYTOOLAI_ENABLED_PRODUCT_IDS", "does_not_exist")
    with pytest.raises(ValueError, match="Unknown enabled product ids: does_not_exist"):
        create_app()
```

Reject empty CSV members such as `proposal_ai,,brief_decoder`; do not silently reinterpret malformed operator input.

- [ ] **Step 2: Implement settings loading once at app creation**

Extend `Settings.from_env()` rather than adding another settings class:

```python
class Settings(BaseModel):
    enabled_product_ids: frozenset[str] | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        values = {
            field: os.environ[env_name]
            for env_name, field in ATOM_LAB_RUN_LIMIT_ENV_FIELDS.items()
            if env_name in os.environ
        }
        if "ANYTOOLAI_ENABLED_PRODUCT_IDS" in os.environ:
            values["enabled_product_ids"] = parse_product_ids(
                os.environ["ANYTOOLAI_ENABLED_PRODUCT_IDS"]
            )
        return cls.model_validate(values)
```

In `create_app()`, load settings after the registry, reject `enabled_product_ids - registry.products.keys()`, and store the result on `app.state.settings`. Change `get_settings(request: Request)` to return that stored instance; retain dependency overrides used by existing tests.

- [ ] **Step 3: Add failing endpoint admission tests**

With `ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai`, assert all three calls for `client_update_writer` return the same safe 404 before their underlying services run:

```text
GET  /v1/products/client_update_writer/runtime-config
GET  /v1/products/client_update_writer/quota?guest_id=guest_1
POST /v1/products/client_update_writer/scenarios/client_update_writer.update_v1/start
```

For quota and scenario start, spy on the service/repository constructor or inspect the database to prove no usage/session/job row was created. Also assert Proposal AI still reaches the existing route behavior.

- [ ] **Step 4: Add the shared enabled-product dependency**

```python
def require_enabled_product(
    product_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if settings.enabled_product_ids is not None and product_id not in settings.enabled_product_ids:
        raise ApiError(status_code=404, code="product_not_found", message="Product not found")
    return product_id
```

Replace each of the three route function's plain `product_id: str` parameters with `Annotated[str, Depends(require_enabled_product)]`. Do not apply this dependency to polling/results/handoff routes that operate on already-created opaque ids.

- [ ] **Step 5: Run focused API tests**

Run:

```powershell
python -m pytest apps/platform-api/tests/test_runtime_config.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_scenario_runtime_api.py apps/platform-api/tests/test_atom_lab_runs.py -q
```

Expected: all pass, including existing Settings dependency overrides.

- [ ] **Step 6: Commit Task 3**

```powershell
git add apps/platform-api/src/anytoolai_platform_api/settings.py apps/platform-api/src/anytoolai_platform_api/main.py apps/platform-api/src/anytoolai_platform_api/dependencies.py apps/platform-api/src/anytoolai_platform_api/routers/runtime_config.py apps/platform-api/src/anytoolai_platform_api/routers/identity_quota.py apps/platform-api/src/anytoolai_platform_api/routers/scenario_runtime.py apps/platform-api/tests/test_runtime_config.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_scenario_runtime_api.py
git commit -m "feat: gate product API routes by release allowlist"
```

---

### Task 4: Apply the web allowlist and support unmetered runtime config

**Files:**

- Modify: `apps/web-mirror/src/products/registry.ts`
- Modify: `apps/web-mirror/src/products/runtime/ProductRunPage.tsx`
- Modify: `apps/web-mirror/test/fixtures/platformResponses.ts`
- Modify: `apps/web-mirror/test/registry.test.tsx`
- Modify: `apps/web-mirror/test/HomePage.test.tsx`
- Modify: `apps/web-mirror/test/ProductRunPage.test.tsx`

**Interfaces:**

- Consumes: `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` at module/build time.
- Preserves: `listRegisteredProducts()` returns every registry entry.
- Produces: `getRegisteredProduct()` returns `null` for disabled entries.
- Consumes: existing `RuntimeConfig.quotaSummary: RuntimeQuotaSummary | null`.

- [ ] **Step 1: Add failing registry tests with isolated module imports**

Use `vi.resetModules()` and dynamic imports so each environment value is evaluated afresh:

```typescript
it("enables every product when the variable is absent", async () => {
  vi.unstubAllEnvs();
  vi.resetModules();
  const registry = await import("../src/products/registry");
  expect(registry.listRegisteredProducts().every((product) => product.enabled)).toBe(true);
});

it("keeps the complete list but disables products outside the allowlist", async () => {
  vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS", "proposal_ai");
  vi.resetModules();
  const registry = await import("../src/products/registry");
  expect(registry.listRegisteredProducts().map((product) => product.productId)).toEqual(
    expect.arrayContaining(["proposal_ai", "client_update_writer"]),
  );
  expect(registry.getRegisteredProduct("proposal_ai")?.enabled).toBe(true);
  expect(registry.getRegisteredProduct("client_update_writer")).toBeNull();
});
```

Restore environment/module state in `afterEach`.

- [ ] **Step 2: Implement registry enablement without filtering**

```typescript
const configuredIds = process.env.NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS;
const enabledIds = configuredIds === undefined
  ? null
  : new Set(configuredIds.split(",").map((id) => id.trim()).filter(Boolean));

const PRODUCT_DEFINITIONS: readonly Omit<RegisteredProduct, "enabled">[] = [
  { productId: "proposal_ai", messages: PROPOSAL_AI_MESSAGES, Component: ProposalAIProduct },
  {
    productId: "client_update_writer",
    messages: CLIENT_UPDATE_WRITER_MESSAGES,
    Component: ClientUpdateWriterProduct,
  },
];

const PRODUCTS: readonly RegisteredProduct[] = PRODUCT_DEFINITIONS.map((product) => ({
  ...product,
  enabled: enabledIds === null || enabledIds.has(product.productId),
}));
```

Keep `listRegisteredProducts(): readonly RegisteredProduct[] { return PRODUCTS; }`. The existing home-page filter and direct-route `getRegisteredProduct()` then share the same `enabled` field.

- [ ] **Step 3: Add a Home page test for a disabled card**

Mock or isolate the registry with only `proposal_ai` enabled, render `HomePage`, and assert Proposal AI is linked while Client Update Writer is absent. Keep the existing default-all test unchanged.

- [ ] **Step 4: Make the default runtime fixture metered and add failing unmetered tests**

Change `runtimeConfigResponse()`'s default `quota_summary` to the existing three-run policy so current quota tests retain their meaning:

```typescript
quota_summary: {
  quota_policy_id: `${ids.productId}.guest_quota_v1`,
  unit: "scenario_run",
  limit_count: 3,
  period: "lifetime",
  dimension: "product",
},
```

Add one boot test with `{ quota_summary: null }` and no queued quota response; assert the form appears and captured calls contain no `ROUTES.QUOTA`. Add one successful-run test that clicks “Start another run” and again asserts zero quota calls.

- [ ] **Step 5: Guard both quota reads from the resolved runtime config**

Extend ready boot state with the backend-owned fact:

```typescript
type BootState =
  | { kind: "loading" }
  | { kind: "boot-error" }
  | { kind: "ready"; scenarioId: string; frontendId: string; hasQuota: boolean };
```

Set `hasQuota: runtimeResult.value.quotaSummary !== null`. On initial load, call `getQuota` only when `resolvedGuestId && runtimeResult.value.quotaSummary !== null`. In `handleStartAnother`, reset the form/result as today, then return before `getQuota` unless `boot.kind === "ready" && boot.hasQuota`.

- [ ] **Step 6: Run focused frontend tests**

Run:

```powershell
pnpm --filter @anytoolai/web-mirror test -- registry.test.tsx HomePage.test.tsx ProductRunPage.test.tsx
pnpm --filter @anytoolai/web-mirror typecheck
```

Expected: complete-registry translation behavior remains intact; metered tests still make quota calls; unmetered tests make none.

- [ ] **Step 7: Commit Task 4**

```powershell
git add apps/web-mirror/src/products/registry.ts apps/web-mirror/src/products/runtime/ProductRunPage.tsx apps/web-mirror/test/fixtures/platformResponses.ts apps/web-mirror/test/registry.test.tsx apps/web-mirror/test/HomePage.test.tsx apps/web-mirror/test/ProductRunPage.test.tsx
git commit -m "feat: gate web products and support unmetered runs"
```

---

### Task 5: Add the production web image and fail-closed Compose contract

**Files:**

- Create: `infra/docker/web-mirror.Dockerfile`
- Modify: `.dockerignore`
- Modify: `infra/compose/docker-compose.prod.yml`
- Modify: `infra/compose/.env.example`
- Modify: `.github/workflows/backend.yml`
- Modify: `scripts/agent/runner.py`
- Modify: `tests/test_runner.py`

**Interfaces:**

- Consumes: `ANYTOOLAI_ENABLED_PRODUCT_IDS`, `ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT`, and existing PostgreSQL values.
- Produces: loopback web endpoint `ANYTOOLAI_PROD_WEB_PORT` (default `3000`).
- Produces: explicit credential-free `prod-fake-up` for the required Compose smoke only.

- [ ] **Step 1: Add failing production Compose/runner assertions**

Test that rendered command/environment contracts require:

- non-empty `ANYTOOLAI_ENABLED_PRODUCT_IDS` for API and web build;
- non-empty `ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT`;
- loopback-only API and web host bindings;
- no published PostgreSQL port;
- blank Demo, Atom Lab, and live-canary access codes;
- web build arg set before build;
- `prod-fake-up` selects only base + prod Compose, never the live overlay.

Use `docker compose config --quiet` in the verification step for YAML semantics; keep unit tests to runner command selection and preflight so they do not require Docker.

- [ ] **Step 2: Create the minimal multi-stage web Dockerfile**

Use the repository's pinned pnpm version through Corepack and copy the workspace once:

```dockerfile
FROM node:22-slim AS build
WORKDIR /app
RUN corepack enable
COPY . .
RUN pnpm install --frozen-lockfile
ARG PLATFORM_API_BASE_URL=http://platform-api:8000
ARG NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
ENV PLATFORM_API_BASE_URL=$PLATFORM_API_BASE_URL
ENV NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS=$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS
RUN test -n "$NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS"
RUN pnpm --filter @anytoolai/web-mirror build

FROM node:22-slim AS runtime
WORKDIR /app
RUN corepack enable
ENV NODE_ENV=production
COPY --from=build /app /app
EXPOSE 3000
CMD ["pnpm", "--filter", "@anytoolai/web-mirror", "exec", "next", "start", "-p", "3000"]
```

Do not add standalone-output tuning or pruning in this feature; the approved spec makes image optimization a non-goal.

Add `.agent/` to `.dockerignore` before building. The generated tree is a runtime bind mount and must not be captured in API, worker, or web build contexts.

- [ ] **Step 3: Extend production Compose**

Apply these exact contracts:

```yaml
services:
  platform-api:
    environment:
      ANYTOOLAI_ENABLED_PRODUCT_IDS: ${ANYTOOLAI_ENABLED_PRODUCT_IDS:?enabled products are required}
      ANYTOOLAI_DEMO_ACCESS_CODE: ""
      ANYTOOLAI_ATOM_LAB_ACCESS_CODE: ""
      ANYTOOLAI_LIVE_CANARY_TOKEN: ""
    ports: !override
      - "127.0.0.1:${ANYTOOLAI_PROD_API_PORT:-8000}:8000"
  platform-worker:
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: ${ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT:?worker memory limit is required}
  web-mirror:
    build:
      context: ../..
      dockerfile: infra/docker/web-mirror.Dockerfile
      args:
        PLATFORM_API_BASE_URL: http://platform-api:8000
        NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS: ${ANYTOOLAI_ENABLED_PRODUCT_IDS:?enabled products are required}
    depends_on:
      platform-api:
        condition: service_healthy
    ports:
      - "127.0.0.1:${ANYTOOLAI_PROD_WEB_PORT:-3000}:3000"
    restart: unless-stopped
```

Add a bounded Node-based healthcheck for `/`; do not install curl solely for healthchecking.

- [ ] **Step 4: Preserve the credential-free required Compose smoke**

Add explicit `prod-fake-up` which retains the old base + production overlay behavior and never falls back from `prod-up`. Update `.github/workflows/backend.yml`'s `compose-smoke-prod` job to call it with:

```yaml
ANYTOOLAI_ENABLED_PRODUCT_IDS: kernel_demo
ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT: 512M
```

Keep `OPENAI_API_KEY` and proxy absent. `prod-smoke` continues to drive `kernel_demo`; `prod-up` is reserved for the real live deployment and must fail when live inputs are absent.

- [ ] **Step 5: Update `.env.example`**

Add names and safe examples only:

```dotenv
ANYTOOLAI_ENABLED_PRODUCT_IDS=proposal_ai
ANYTOOLAI_UNMETERED_PRODUCT_IDS=proposal_ai
ANYTOOLAI_LLM_HTTPS_PROXY=http://proxy-host:3128
ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT=768M
ANYTOOLAI_PROD_API_PORT=8000
ANYTOOLAI_PROD_WEB_PORT=3000
```

Keep `OPENAI_API_KEY`, proxy credentials, and real database credentials blank.

- [ ] **Step 6: Render and build the production web service**

Run with disposable values:

```powershell
$env:ANYTOOLAI_POSTGRES_USER='ci'
$env:ANYTOOLAI_POSTGRES_PASSWORD='ci'
$env:ANYTOOLAI_POSTGRES_DB='ci'
$env:ANYTOOLAI_ENABLED_PRODUCT_IDS='proposal_ai'
$env:ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT='768M'
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml config --quiet
docker compose -f infra/compose/docker-compose.yml -f infra/compose/docker-compose.prod.yml build web-mirror
```

Then unset `ANYTOOLAI_ENABLED_PRODUCT_IDS` and confirm both Compose interpolation and a direct Docker build without `NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS` fail.

- [ ] **Step 7: Commit Task 5**

```powershell
git add .dockerignore infra/docker/web-mirror.Dockerfile infra/compose/docker-compose.prod.yml infra/compose/.env.example .github/workflows/backend.yml scripts/agent/runner.py tests/test_runner.py
git commit -m "feat: add fail-closed production web stack"
```

---

### Task 6: Complete production live preflight, profile checks, and readiness

**Files:**

- Modify: `scripts/agent/runner.py`
- Modify: `tests/test_runner.py`
- Verify: `infra/compose/docker-compose.live.yml`
- Verify: `infra/compose/docker-compose.prod.yml`

**Interfaces:**

- Consumes: Tasks 1, 2, and 5 profile/check/Compose interfaces.
- Produces: fail-closed `prod-up` with resolved allowlist/quota output.
- Produces: `prod-ready` that waits for API and web, then validates API and worker profile mounts before reporting ready.

- [ ] **Step 1: Add failing production selection/preflight tests**

Add table-driven tests for:

```python
@pytest.mark.parametrize("missing_name", [
    "ANYTOOLAI_POSTGRES_USER",
    "ANYTOOLAI_POSTGRES_PASSWORD",
    "ANYTOOLAI_POSTGRES_DB",
    "OPENAI_API_KEY",
    "ANYTOOLAI_LLM_HTTPS_PROXY",
    "ANYTOOLAI_ENABLED_PRODUCT_IDS",
    "ANYTOOLAI_UNMETERED_PRODUCT_IDS",
    "ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT",
])
def test_prod_up_rejects_missing_required_value_before_compose(missing_name, ...): ...
```

Add separate cases proving:

- `ANYTOOLAI_UNMETERED_PRODUCT_IDS=""` is accepted and prints `proposal_ai=canonical`;
- a shell empty value overrides `.env.prod`'s `proposal_ai` and prints canonical;
- unmetered ids outside enabled ids fail;
- duplicate/empty CSV members fail;
- any nonblank Demo/Atom Lab/live-canary access code fails;
- stdout contains product ids/modes but not OpenAI key, proxy credentials, or DB password;
- no Compose/profile function is called after any preflight failure.

- [ ] **Step 2: Implement resolved deployment inputs**

Use a frozen runner dataclass:

```python
@dataclass(frozen=True)
class DeploymentInputs:
    enabled_product_ids: tuple[str, ...]
    unmetered_product_ids: frozenset[str]
    compose_env: dict[str, str]

    def quota_mode(self, product_id: str) -> str:
        return "unmetered" if product_id in self.unmetered_product_ids else "canonical"
```

Resolve `.env.prod` first and overlay `os.environ` by key presence, not truthiness, so an exported empty string wins. Preserve the missing/empty distinction before validating. Pass the resolved nonsecret selectors into the Compose subprocess environment so generation, API, and web build use the same allowlist.

- [ ] **Step 3: Print safe resolved selection before mutation**

Before profile generation or `_prod_stack_running()`, print only:

```text
Enabled products: proposal_ai
Quota modes: proposal_ai=unmetered
```

For an explicitly empty unmetered list, the second line must say `proposal_ai=canonical`. Never print key, proxy URL, database password, or complete environment mappings.

- [ ] **Step 4: Make live `prod-up` generate first, then compose all three files**

Build `.agent/deployment-profiles/anytoolai-prod/freelancer-suite`, set `ANYTOOLAI_DEPLOYMENT_PRODUCTS_ROOT`, and invoke:

```text
docker compose --project-name anytoolai-prod --env-file infra/compose/.env.prod \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.prod.yml \
  -f infra/compose/docker-compose.live.yml \
  up -d --build --remove-orphans
```

The env-file flag is included only when the file exists. `prod-fake-up` from Task 5 deliberately remains base + prod only.

- [ ] **Step 5: Gate readiness on web and both effective-profile checks**

Refactor the current wait into a non-printing helper and order readiness as:

1. API `/health` returns 200;
2. web `/` returns 200 on the loopback web port;
3. API container profile check passes;
4. worker container profile check passes;
5. print API/web endpoints and “Production environment is ready”.

Any mismatch in mounted path, fingerprint, enabled provider ref, or expected quota ref returns nonzero. A fake policy in Client Update Writer or Brief Decoder is ignored when that product is disabled.

- [ ] **Step 6: Add stale/mount/fake-product tests**

Mock container command results and assert:

- wrong fingerprint fails after health but before ready output;
- wrong bundle root fails;
- `proposal_ai=default_fake_provider_v1` fails;
- disabled `client_update_writer=default_fake_provider_v1` is absent from expectations and passes;
- API and worker receive byte-for-byte identical expectation arguments;
- changing only `ANYTOOLAI_UNMETERED_PRODUCT_IDS` does not add a web rebuild-specific argument.

- [ ] **Step 7: Run production runner and Compose tests**

Run:

```powershell
python -m pytest tests/test_runner.py tests/test_validate_configs.py -q
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-architecture
```

Expected: all pass and canonical validation remains write-free.

- [ ] **Step 8: Commit Task 6**

```powershell
git add scripts/agent/runner.py tests/test_runner.py
git commit -m "feat: orchestrate fail-closed production live deployment"
```

---

### Task 7: Finish operator documentation and end-to-end verification

**Files:**

- Modify: `infra/deployment/README.md`
- Modify: `docs/product-specs/add-product-recipe.md`
- Modify: `docs/exec-plans/active/proposal-ai-vps-live-deployment.md`

**Interfaces:**

- Consumes: all previous tasks.
- Produces: one complete operator runbook and one reusable product-onboarding rule.

- [ ] **Step 1: Update the VPS deployment runbook**

Document exact operator actions:

1. install Docker/Compose and clone the repository;
2. create gitignored `.env.prod` with all required values;
3. verify Squid permits `CONNECT api.openai.com:443` and, for catalog refresh, `raw.githubusercontent.com:443`;
4. run `python scripts/agent/runner.py prod-up` and inspect printed allowlist/quota modes;
5. configure Nginx/Caddy to forward the product domain to `127.0.0.1:${ANYTOOLAI_PROD_WEB_PORT}`;
6. deny `/atom-lab`, Atom Lab static assets, `/v1/atom-lab/*`, and `/v1/demo/*` before forwarding;
7. run browser/API/provider-ledger/Squid-log acceptance checks;
8. measure worker peak memory and check Docker restart/OOM state;
9. switch quota by changing only `ANYTOOLAI_UNMETERED_PRODUCT_IDS`, then rerun `prod-up`;
10. roll back image/Compose revision or remove the live overlay and recreate containers.

State explicitly that runtime proxy variables do not prevent direct egress; firewall policy is required for mandatory no-bypass routing. Explain that Docker pull/build proxy configuration is separate. For TLS-intercepting Squid, give a small operator-owned Compose override that read-only mounts the CA and sets `SSL_CERT_FILE`; do not commit CA material.

- [ ] **Step 2: Document the next-product contract**

In `docs/product-specs/add-product-recipe.md`, add:

- actions using `default_fake_provider_v1` are automatically eligible for the standard live transform;
- canonical quota count/period/dimension stay in the product's YAML;
- deployment only selects canonical versus unmetered;
- a product with no canonical quota remains unmetered in canonical mode;
- a future product needing per-action policies must add an explicit reviewed mapping instead of weakening the strict transform;
- release requires adding the product id to both server/web allowlists, with no proxy/Compose duplication.

- [ ] **Step 3: Run repository gates**

Run in this order:

```powershell
python scripts/agent/runner.py doctor
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
```

Expected: all pass on canonical fake configuration without OpenAI credentials.

- [ ] **Step 4: Run the credential-free production Compose smoke**

Run `prod-fake-up` with disposable PostgreSQL values, `ANYTOOLAI_ENABLED_PRODUCT_IDS=kernel_demo`, and `ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT=512M`; then run `prod-smoke` and `prod-down`.

Expected: `kernel_demo` completes through the real worker without an OpenAI key. This proves production image/Compose wiring while preserving the required credential-free CI gate.

- [ ] **Step 5: Run local live acceptance with real credentials**

With the operator's key/proxy only in shell or `.env.live`:

```powershell
python scripts/agent/runner.py dev-live-up --product proposal_ai
python scripts/agent/runner.py dev-web
```

Submit more than ten Proposal AI runs and confirm no quota call/429, a successful OpenAI provider ledger row, and the corresponding Squid CONNECT entry. Repeat with `--quota-mode canonical` in a bounded test and confirm quota state/exhaustion returns. Finish with `dev-down`, then normal `dev-up`, and confirm fake-backed behavior returns.

- [ ] **Step 6: Run VPS acceptance**

Verify all approved success criteria:

- only Proposal AI is visible and startable;
- direct API calls for disabled products return safe 404;
- API/web bind only to loopback and PostgreSQL is unpublished;
- public Demo/Atom Lab paths are denied and codes are blank;
- worker has key/proxy, API/web do not;
- API and worker report the same profile fingerprint;
- OpenAI succeeds through Squid, with no direct fallback added;
- unmetered runs do not create/decrement usage rows;
- canonical mode reuses pre-window rows while guests first seen unmetered begin at zero;
- worker is neither restarted nor `OOMKilled` during a cold catalog refresh plus real run.

- [ ] **Step 7: Record evidence and complete the plan**

Add a dated progress/result section to this file with command results, live/VPS evidence locations, measured worker peak memory, chosen production memory limit, and any operator-owned reverse-proxy/firewall references. Move the plan to `docs/exec-plans/completed/` only after VPS acceptance succeeds.

- [ ] **Step 8: Commit Task 7**

```powershell
git add infra/deployment/README.md docs/product-specs/add-product-recipe.md docs/exec-plans/active/proposal-ai-vps-live-deployment.md
git commit -m "docs: add Proposal AI live deployment runbook"
```

## Deferred by Design

- No repository-owned Nginx, Caddy, Squid, DNS, TLS automation, or firewall policy.
- No arbitrary YAML patch engine or per-action provider mapping until a product actually needs one.
- No billing/authentication/abuse system beyond the selected canonical anonymous quota.
- No web-image size optimization beyond the correct multi-stage image.
- No LiteLLM Proxy; the existing in-process SDK remains the current runtime boundary.

## Validation

- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py full-check`
- [x] Credential-free production Compose smoke plus `prod-smoke` in a fresh isolated project (see result below)
- [x] Real-provider local live acceptance without Squid (proxy check deferred to VPS by operator)
- [ ] Target-VPS acceptance

## Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-09-25 | Generate profiles from canonical product YAML instead of committing deployment copies. | Prevent drift and keep normal development/CI fake-backed. |
| 2026-09-25 | Keep quota business policy in canonical YAML; deployment selects only canonical or unmetered. | Supports the initial launch and later anonymous limits without migration or duplicated policy. |
| 2026-09-25 | Add explicit `prod-fake-up` for required CI smoke; never make live `prod-up` fall back. | Preserve credential-free CI while keeping real production fail-closed. |

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-09-25 | Design externally reviewed and approved; implementation plan written and self-reviewed. | Choose execution mode and begin Task 1. |
| 2026-09-25 | Task 1: generated live profiles, strict provider/quota transform, deterministic fingerprints, and read-only effective-config check implemented; 32 focused/architecture tests, config validation, and lint passed. | Task 2: local live runner and Compose overlay. |
| 2026-09-25 | Task 2: `dev-live-up`, `dev-web`, shared live overlay, env resolution, and identical API/worker effective-profile checks implemented; runner/profile tests and Compose render passed. | Task 3: Platform API release allowlist. |
| 2026-09-25 | Task 3: server allowlist parses once at startup, rejects unknown ids, and gates runtime config, quota, and scenario start before storage; focused API tests and architecture validation passed. | Task 4: web allowlist and unmetered runtime behavior. |
| 2026-09-25 | Task 4: web registry build-time allowlist and both unmetered quota guards implemented after four failing tests; 249 frontend tests and typecheck passed. | Task 5: production Compose and web image. |
| 2026-09-25 | Task 5: web image and production Compose enforce a nonempty allowlist, loopback API/web ports, unpublished PostgreSQL, blank public access codes, and explicit worker memory; separate `prod-fake-up` powers credential-free CI. Runner tests, Compose contract, image build, and missing-allowlist rejection passed. | Task 6: fail-closed live `prod-up` and effective-profile readiness. |
| 2026-09-25 | Task 6: live `prod-up` now validates credentials, selections, blank public gates, and both host ports before Compose; generates the profile, selects all three overlays, then gates ready on API, web, and identical container checks. 134 runner/profile tests (3 skips), config/architecture validation, and three-file Compose render passed. | Task 7: runbook and end-to-end gates. |
| 2026-09-25 | Task 7: public VPS runbook, next-product live contract, regenerated OpenAPI/client types, and Windows-safe API type generator finished. Doctor, config/architecture/docs, quick-check (1923 passed, 3 skipped), frontend-check, full-check (same baseline plus 99 product tests), and isolated credential-free Compose smoke (11 atoms, 3 composites) passed. | Fresh independent review; local OpenAI and VPS acceptance await operator credentials/access. |
| 2026-09-25 | One fresh independent code review found four deployment defects. Fixed profile replacement across Linux bind mounts with forced Compose recreation and preserved prior directories until readiness; made `prod-ready` reject stale quota selection and canonical source fingerprints; used the bootstrapped managed Python for live profile generation; applied CLI overrides before `dev-live-up` dispatch. Also fixed repeat local live deploys to recognize their own occupied ports. Focused tests passed; config, architecture, and docs validations passed; repeated quick-check (1929 passed, 3 skipped), full-check (same baseline, frontend checks, 99 product tests), and a fresh credential-free production Compose smoke (11 atoms, 3 composites) passed. | Run real local OpenAI/Squid and target-VPS acceptance with operator credentials/access. |
| 2026-09-25 | Local direct-OpenAI acceptance passed with the operator's gitignored `.env.live`: 11 unmetered runs completed with no guest quota usage; the browser submitted successfully without a quota request; 10 canonical runs completed and the next start returned HTTP 429. Ordinary `dev-up` subsequently completed a run through `default_fake_provider_v1`. The local Compose stack was stopped without deleting its PostgreSQL volume. The operator deferred Squid verification to VPS deployment. | Confirm shared HAProxy connectivity and complete target-VPS acceptance. |
| 2026-09-25 | PR review follow-up: isolated Atom Lab limit parsing from public API startup; replaced the dotenv approximation with Docker Compose's own resolved environment; passed the production product allowlist into worker and terminalized queued jobs for disabled products before execution. Focused API, worker settings, runner tests and config, architecture, docs validations passed. PostgreSQL worker regression remains for CI. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Second PR review follow-up: serialized disabled-job terminalization with the advisory lease and preserved full scenario event context; verified the two-worker regression against local disposable PostgreSQL. Restored literal dollar signs after Compose environment resolution. Made generated profile directories immutable and versioned, with the active marker and old-profile cleanup only after successful readiness; runner/profile tests passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Third PR review follow-up: `prod-up` now tears down a candidate after Compose startup or readiness failure, preserving the PostgreSQL volume; production and credential-free readiness probe the product runtime-config through web, and the web container healthcheck verifies the same-origin API response. Focused runner tests and credential-free Compose render passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Fourth PR review follow-up: handoff acceptance checks the persisted token's source and target against the API release allowlist before creating a target session, job, or quota usage. API and worker now verify the versioned live profile manifest and mounted configs before serving or polling; ordinary fake-backed startup remains unchanged. Focused PostgreSQL handoff and profile/runner tests passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Fifth PR review follow-up: merged current `main` and retained both live-canary test additions. Profile cleanup errors are warnings after activation; generated manifests use mode `0644` for the non-root API; failed local-live starts stop Compose and clear stale web selection; `dev-web` derives the active product list; the web registry rejects unknown public enabled IDs during production build. Focused runner/profile/web tests passed; a `brief_decoder` web build failed as expected, while `proposal_ai` and backend-only CI `kernel_demo` builds passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Sixth PR review follow-up: synchronized the collaborator's isolated `prod-fake-up` fixes. The three failing CI jobs had the same two runner-test failures: stale `_prod_fake_ready()` mocks did not accept the new resolved `env` argument. Updated both tests to pass and assert the shared environment; local-live activation now reports `LIVE005` and stops the candidate on marker or profile errors. Focused regressions passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Seventh PR review follow-up: `prod-fake-up` now overrides production credentials, key, and product selection with disposable fake-smoke values and never gives `.env.prod` to Compose; Compose teardown gets 180 seconds so the worker's 60-second stop grace can complete. Runner regression tests passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Eighth PR review follow-up: merged current `main` with the Brief Decoder web product and resolved both overlapping runner/runbook edits. Generated non-secret product configuration is now normalized to traversable directories and readable files after the live transform; the profile tests passed. | Gate candidate worker queue polling on profile activation, then confirm CI and VPS acceptance. |
| 2026-09-25 | Candidate live worker now verifies its mounted profile and waits for `active-profile` to select its generation before starting queue polling; failed candidates cannot terminalize queued jobs. Runner regressions, three-file Compose render, and entrypoint shell syntax passed. | Confirm CI and complete target-VPS acceptance. |
| 2026-09-25 | Post-merge CI diagnosis: six jobs failed on the same TypeScript error because Brief Decoder's newly merged registry entry still set `enabled` while the release allowlist computes it. Removed the stale field and updated the unknown-product regression; web typecheck and all 277 web tests passed. The merged backend quick-check passed with 2000 tests (4 skipped). | Confirm rerun CI and complete target-VPS acceptance. |

## Verification Result (2026-09-25)

- `docker compose` rendered the production base + prod + live stack with disposable values. The web image built with `proposal_ai`; missing web allowlist failed both Compose interpolation and direct Docker build. Resolved production Compose bound API/web to loopback, published no PostgreSQL port, blanked public access codes, and applied the worker memory limit.
- `prod-fake-up` on the fixed `anytoolai-prod` project could not complete because its PostgreSQL volume predates this task (created 2026-07-28) and was not removed or modified. The same base + prod Compose stack was started in a fresh disposable project with no OpenAI key or proxy; API/web health, `prod-smoke` (11/11 standalone atoms and 3/3 composite workflows), and teardown all passed. Runner command-selection tests prove `prod-fake-up` uses exactly those two Compose files.
- After review fixes, the same credential-free smoke was repeated in disposable project `anytoolai-review-724a5f31`: API/web health and `prod-smoke` passed (11/11 atoms, 3/3 composites), and the project volume was removed. Post-review `quick-check` and `full-check` both passed with 1929 backend tests (3 skipped); the latter also passed the frontend gates and 99 product tests.
- Local `dev-live-up --product proposal_ai` used the operator's gitignored OpenAI key with an empty proxy setting. Eleven unmetered Proposal AI sessions completed with eleven successful OpenAI provider-call rows and no guest quota usage rows. A browser submission on the local web page returned HTTP 200, produced a nonempty result, and made no quota request. Switching to `--quota-mode canonical` preserved the guest at zero initial usage; ten more real sessions completed, quota reported `used_count=10`, `remaining_count=0`, and an eleventh start returned HTTP 429. `dev-down`, ordinary `dev-up`, and a new Proposal AI run succeeded with provider ledger `default_fake_provider_v1|fake|fake-json-v1|succeeded`; the final `dev-down` retained the PostgreSQL volume.
- The operator deferred forward-proxy verification to VPS deployment. Squid CONNECT evidence, target-VPS acceptance, worker peak memory, production memory limit, and reverse-proxy/firewall references remain outstanding. The proposed shared HAProxy arrangement on the PromptTune VPS is not yet implemented or verified. This plan remains active until target-VPS acceptance is complete.

## Open Questions

- None blocking. Squid CA mounting remains an operator-only override unless the deployed Squid is confirmed to perform TLS interception.

## Follow-up Debt

- None created by the plan; deferred items are explicit non-goals above.
