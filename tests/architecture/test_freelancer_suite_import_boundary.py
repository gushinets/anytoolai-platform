from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def validate_architecture_module():
    path = ROOT / "scripts" / "agent" / "validate_architecture.py"
    spec = importlib.util.spec_from_file_location("validate_architecture_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_freelancer_suite_is_imported_only_from_the_composition_boundaries(
    validate_architecture_module,
) -> None:
    """ANY-32: anytoolai_freelancer_suite is a product bundle package -- only the three
    runtime/validation composition boundaries (apps/platform-api/bootstrap.py,
    apps/platform-worker/composition.py, scripts/agent/validate_configs.py) may import it.
    Real-repo check; the regression fixtures below prove the AST-based detection itself works."""
    errors = validate_architecture_module.check_freelancer_suite_import_boundary(
        [ROOT / "apps", ROOT / "packages", ROOT / "scripts", ROOT / "extensions"]
    )

    assert errors == [], "unexpected anytoolai_freelancer_suite importer(s): " + ", ".join(errors)


def test_loader_and_registry_extension_points_stay_bundle_ignorant() -> None:
    """The new multi-root extension points this ticket added (ConfigLoader.extra_product_roots,
    build_config_registry's extra_product_roots passthrough) must not gain a bundle-specific
    import or literal -- platform-core stays Path-only and ProductBundle-ignorant."""
    loader_path = (
        ROOT
        / "packages"
        / "backend"
        / "platform-core"
        / "src"
        / "anytoolai_platform_core"
        / "config"
        / "loader.py"
    )
    registry_path = (
        ROOT
        / "packages"
        / "backend"
        / "platform-core"
        / "src"
        / "anytoolai_platform_core"
        / "bootstrap"
        / "registry.py"
    )
    forbidden = ["anytoolai_freelancer", "FreelancerSuiteBundle"]
    for path in (loader_path, registry_path):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} contains forbidden bundle-specific token {token}"


def test_forbidden_import_is_detected(
    validate_architecture_module, monkeypatch, tmp_path: Path
) -> None:
    # SKIP_PATH_PARTS excludes scratch/build directory names (e.g. ".quick-check-tmp") that can
    # also appear as ancestors of pytest's tmp_path -- drop only the entries that actually
    # collide with tmp_path's own location, mirroring
    # test_product_platforms_has_no_forbidden_imports.py's own _check_over_tmp_path helper.
    skip_path_parts = validate_architecture_module.SKIP_PATH_PARTS
    colliding = {part for part in tmp_path.parts if part in skip_path_parts}
    monkeypatch.setattr(
        validate_architecture_module,
        "SKIP_PATH_PARTS",
        validate_architecture_module.SKIP_PATH_PARTS - colliding,
    )
    (tmp_path / "offending_module.py").write_text(
        "from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle\n",
        encoding="utf-8",
    )

    errors = validate_architecture_module.check_freelancer_suite_import_boundary([tmp_path])

    assert len(errors) == 1
    assert errors[0].startswith("ATAI008 ")
    assert "anytoolai_freelancer_suite" in errors[0]


def test_bootstrap_own_import_is_not_flagged(validate_architecture_module) -> None:
    errors = validate_architecture_module.check_freelancer_suite_import_boundary(
        [ROOT / "apps" / "platform-api"]
    )

    assert errors == []


def test_worker_composition_own_import_is_not_flagged(validate_architecture_module) -> None:
    errors = validate_architecture_module.check_freelancer_suite_import_boundary(
        [ROOT / "apps" / "platform-worker"]
    )

    assert errors == []


def test_validate_configs_own_import_is_not_flagged(validate_architecture_module) -> None:
    errors = validate_architecture_module.check_freelancer_suite_import_boundary(
        [ROOT / "scripts"]
    )

    assert errors == []


def test_freelancer_suite_own_source_and_tests_are_not_flagged(
    validate_architecture_module,
) -> None:
    errors = validate_architecture_module.check_freelancer_suite_import_boundary(
        [ROOT / "packages" / "backend" / "product-platforms" / "freelancer-suite"]
    )

    assert errors == []
