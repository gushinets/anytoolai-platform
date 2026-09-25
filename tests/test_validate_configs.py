from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PureWindowsPath

import pytest
import yaml

from scripts.agent import validate_configs

PRODUCTS_ROOT = (
    validate_configs.ROOT
    / "packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products"
)


def generated_product(output_dir: Path, product_id: str) -> Path:
    return output_dir / "products" / product_id


def generated_action_refs(output_dir: Path, product_id: str) -> set[str]:
    payload = yaml.safe_load(
        (generated_product(output_dir, product_id) / "action_configs.yaml").read_text()
    )
    return {item["provider_policy_ref"] for item in payload["action_configs"]}


def test_default_validation_does_not_create_a_deployment_profile(monkeypatch, tmp_path):
    monkeypatch.setattr(validate_configs, "ROOT", tmp_path)
    monkeypatch.setattr(validate_configs, "load_registry", lambda: None)
    monkeypatch.setattr(validate_configs, "load_model_capability_overrides", lambda _path: object())

    assert validate_configs.main([]) == 0
    assert not (tmp_path / ".agent").exists()


def test_tree_fingerprint_uses_posix_relative_paths_and_exact_bytes(tmp_path):
    root = tmp_path / "products"
    (root / "nested").mkdir(parents=True)
    path = root / "nested" / "a.yaml"
    path.write_bytes(b"x\r\ny\n")

    first = validate_configs.tree_fingerprint(root)
    assert validate_configs.normalized_relative_path(root, path) == "nested/a.yaml"
    assert first == "00bff2c995b88fa0e64c19d3f9d02105190c40d9f0921d54ea0e4c53f881a21e"
    assert validate_configs.tree_fingerprint(root) == first

    path.write_bytes(b"x\ny\n")
    assert validate_configs.tree_fingerprint(root) != first


def test_tree_fingerprint_ignores_file_creation_order(tmp_path):
    names = ("z.yaml", "a.yaml")
    roots = (tmp_path / "first", tmp_path / "second")
    for root, order in zip(roots, (names, reversed(names)), strict=True):
        root.mkdir()
        for name in order:
            (root / name).write_bytes(name.encode())

    assert validate_configs.tree_fingerprint(roots[0]) == validate_configs.tree_fingerprint(
        roots[1]
    )


def test_normalized_relative_path_is_identical_for_windows_and_posix_paths():
    assert (
        validate_configs.normalized_relative_path(
            PureWindowsPath(r"C:\source\products"),
            PureWindowsPath(r"C:\source\products\nested\a.yaml"),
        )
        == "nested/a.yaml"
    )


def test_tree_fingerprint_has_independent_length_prefixed_expected_value(tmp_path):
    root = tmp_path / "products"
    root.mkdir()
    (root / "a").write_bytes(b"bc")
    digest = hashlib.sha256()
    digest.update((1).to_bytes(8, "big") + b"a" + (2).to_bytes(8, "big") + b"bc")

    assert validate_configs.tree_fingerprint(root) == digest.hexdigest()


def test_build_profile_transforms_only_enabled_product_and_preserves_full_tree(tmp_path):
    output_dir = tmp_path / "freelancer-suite"

    manifest = validate_configs.build_deployment_profile(
        output_dir, ["proposal_ai"], {"proposal_ai"}
    )

    assert generated_action_refs(output_dir, "proposal_ai") == {"default_text_generation_v1"}
    assert generated_action_refs(output_dir, "client_update_writer") == {"default_fake_provider_v1"}
    product = yaml.safe_load(
        (generated_product(output_dir, "proposal_ai") / "product.yaml").read_text()
    )
    quotas = yaml.safe_load(
        (generated_product(output_dir, "proposal_ai") / "quotas.yaml").read_text()
    )
    assert "quota_policy_ref" not in product
    assert quotas["quota_policies"] == []
    assert manifest.enabled_products["proposal_ai"].quota_policy_ref is None
    assert manifest.source_fingerprint == validate_configs.tree_fingerprint(PRODUCTS_ROOT)
    assert manifest.profile_fingerprint == validate_configs.tree_fingerprint(
        output_dir / "products"
    )
    assert (
        generated_product(output_dir, "proposal_ai") / "prompts/compose_persuasive_text.v1.md"
    ).read_bytes() == (
        PRODUCTS_ROOT / "proposal_ai/prompts/compose_persuasive_text.v1.md"
    ).read_bytes()
    saved = json.loads((output_dir / "manifest.json").read_text())
    assert saved["enabled_products"]["proposal_ai"] == {
        "provider_policy_ref": "default_text_generation_v1",
        "quota_policy_ref": None,
    }


def test_build_profile_canonical_mode_preserves_quota_files(tmp_path):
    output_dir = tmp_path / "freelancer-suite"

    manifest = validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], set())

    assert manifest.enabled_products["proposal_ai"].quota_policy_ref == "proposal_ai.guest_quota_v1"
    for name in ("product.yaml", "quotas.yaml"):
        assert (generated_product(output_dir, "proposal_ai") / name).read_bytes() == (
            PRODUCTS_ROOT / "proposal_ai" / name
        ).read_bytes()


def test_build_profile_unmetered_product_with_no_canonical_quota(tmp_path):
    output_dir = tmp_path / "freelancer-suite"

    manifest = validate_configs.build_deployment_profile(
        output_dir, ["client_update_writer"], {"client_update_writer"}
    )

    assert manifest.enabled_products["client_update_writer"].quota_policy_ref is None
    assert yaml.safe_load(
        (generated_product(output_dir, "client_update_writer") / "quotas.yaml").read_text()
    ) == {"quota_policies": []}


@pytest.mark.parametrize(
    ("enabled", "unmetered", "message"),
    [
        (["missing"], set(), "unknown product"),
        (["proposal_ai"], {"brief_decoder"}, "must be a subset"),
        ([], set(), "enabled product"),
        (["proposal_ai", "proposal_ai"], set(), "duplicate"),
    ],
)
def test_build_profile_fails_closed(tmp_path, enabled, unmetered, message):
    with pytest.raises(ValueError, match=message):
        validate_configs.build_deployment_profile(tmp_path / "freelancer-suite", enabled, unmetered)


def test_build_profile_rejects_product_without_standard_fake_policy(monkeypatch, tmp_path):
    fixture_package = tmp_path / "fixture_package"
    fixture_products = fixture_package / "products"
    fixture_products.mkdir(parents=True)
    shutil.copytree(PRODUCTS_ROOT / "proposal_ai", fixture_products / "proposal_ai")
    action_path = fixture_products / "proposal_ai/action_configs.yaml"
    action_path.write_text(
        action_path.read_text().replace("default_fake_provider_v1", "default_text_generation_v1")
    )
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle, "_package_dir", lambda self: fixture_package
    )
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle,
        "config_roots",
        lambda self: [fixture_products / "proposal_ai"],
    )

    with pytest.raises(ValueError, match="no action config uses default_fake_provider_v1"):
        validate_configs.build_deployment_profile(
            tmp_path / "freelancer-suite", ["proposal_ai"], set()
        )


def test_failed_profile_rebuild_keeps_previous_valid_profile(monkeypatch, tmp_path):
    output_dir = tmp_path / "freelancer-suite"
    first = validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], set())
    before = (output_dir / "manifest.json").read_bytes()
    monkeypatch.setattr(
        validate_configs,
        "_transform_live_product",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad transform")),
    )

    with pytest.raises(ValueError, match="bad transform"):
        validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], {"proposal_ai"})

    assert (output_dir / "manifest.json").read_bytes() == before
    assert validate_configs.tree_fingerprint(output_dir / "products") == first.profile_fingerprint


def test_profile_manifest_records_selected_quota_mode(tmp_path):
    manifest = validate_configs.build_deployment_profile(
        tmp_path / "freelancer-suite", ["proposal_ai"], {"proposal_ai"}
    )
    assert manifest.unmetered_product_ids == ("proposal_ai",)


def test_profile_rebuild_never_replaces_existing_bind_source(tmp_path):
    output_dir = tmp_path / "freelancer-suite"
    first = validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], {"proposal_ai"})
    with pytest.raises(ValueError, match="already exists"):
        validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], set())
    assert validate_configs.tree_fingerprint(output_dir / "products") == first.profile_fingerprint


def test_source_fingerprint_check_rejects_changed_tree(tmp_path):
    source = tmp_path / "products"
    source.mkdir()
    (source / "product.yaml").write_text("product_id: proposal_ai\n", encoding="utf-8")
    expected = validate_configs.tree_fingerprint(source)
    validate_configs.check_source_fingerprint(source, expected)
    (source / "product.yaml").write_text("product_id: changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="source fingerprint mismatch"):
        validate_configs.check_source_fingerprint(source, expected)


def test_check_deployment_profile_reads_resolved_bundle_and_ignores_disabled_fake(
    monkeypatch, tmp_path
):
    output_dir = tmp_path / "freelancer-suite"
    manifest = validate_configs.build_deployment_profile(
        output_dir, ["proposal_ai"], {"proposal_ai"}
    )
    products_root = output_dir / "products"
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle,
        "_package_dir",
        lambda self: output_dir,
    )
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle,
        "config_roots",
        lambda self: [
            products_root / name
            for name in ("proposal_ai", "client_update_writer", "brief_decoder")
        ],
    )

    validate_configs.check_deployment_profile(
        products_root,
        manifest.profile_fingerprint,
        manifest.enabled_products,
    )
    with pytest.raises(ValueError, match="fingerprint"):
        validate_configs.check_deployment_profile(
            products_root, "0" * 64, manifest.enabled_products
        )
    with pytest.raises(ValueError, match="expected quota policy"):
        validate_configs.check_deployment_profile(
            products_root,
            manifest.profile_fingerprint,
            {
                "proposal_ai": validate_configs.ProductProfileExpectation(
                    "default_text_generation_v1", "proposal_ai.guest_quota_v1"
                )
            },
        )


def test_check_deployment_profile_rejects_wrong_bundle_root(tmp_path):
    output_dir = tmp_path / "freelancer-suite"
    manifest = validate_configs.build_deployment_profile(output_dir, ["proposal_ai"], set())

    with pytest.raises(ValueError, match="resolved bundle products root"):
        validate_configs.check_deployment_profile(
            output_dir / "products", manifest.profile_fingerprint, manifest.enabled_products
        )


def test_startup_profile_check_rejects_stale_mount_and_selection(monkeypatch, tmp_path):
    output_dir = tmp_path / "freelancer-suite"
    manifest = validate_configs.build_deployment_profile(
        output_dir, ["proposal_ai"], {"proposal_ai"}
    )
    products_root = output_dir / "products"
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle, "_package_dir", lambda self: output_dir
    )
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle,
        "config_roots",
        lambda self: [
            products_root / name
            for name in ("proposal_ai", "client_update_writer", "brief_decoder")
        ],
    )
    monkeypatch.setattr(validate_configs, "CONTAINER_PRODUCTS_ROOT", products_root)
    check = [
        "check-deployment-profile-from-manifest",
        "--manifest",
        str(output_dir / "manifest.json"),
        "--expected-fingerprint",
        manifest.profile_fingerprint,
        "--enabled-products",
        "proposal_ai",
        "--unmetered-products",
        "proposal_ai",
    ]
    saved = json.loads((output_dir / "manifest.json").read_text())
    saved["container_products_root"] = products_root.as_posix()
    (output_dir / "manifest.json").write_text(json.dumps(saved))
    assert validate_configs.main(check) == 0
    assert validate_configs.main([*check[:4], "0" * 64, *check[5:]]) == 1
    assert validate_configs.main([*check[:-1], ""]) == 1
    (products_root / "proposal_ai" / "action_configs.yaml").write_text("action_configs: []\n")
    assert validate_configs.main(check) == 1


def test_profile_cli_build_and_check_fail_closed(monkeypatch, tmp_path, capsys):
    output_dir = tmp_path / "freelancer-suite"
    assert (
        validate_configs.main(
            [
                "build-deployment-profile",
                "--output-dir",
                str(output_dir),
                "--enabled-product",
                "proposal_ai",
                "--unmetered-product",
                "proposal_ai",
            ]
        )
        == 0
    )
    manifest = json.loads((output_dir / "manifest.json").read_text())
    products_root = output_dir / "products"
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle, "_package_dir", lambda self: output_dir
    )
    monkeypatch.setattr(
        validate_configs.FreelancerSuiteBundle,
        "config_roots",
        lambda self: [
            products_root / name
            for name in ("proposal_ai", "client_update_writer", "brief_decoder")
        ],
    )
    args = [
        "check-deployment-profile",
        "--products-root",
        str(products_root),
        "--expected-fingerprint",
        manifest["profile_fingerprint"],
        "--expect-product",
        "proposal_ai=default_text_generation_v1,-",
    ]
    assert validate_configs.main(args) == 0
    assert validate_configs.main(args[:-1] + ["proposal_ai=default_fake_provider_v1,-"]) == 1
    assert "expected default_fake_provider_v1" in capsys.readouterr().err
