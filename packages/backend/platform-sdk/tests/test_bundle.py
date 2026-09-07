from __future__ import annotations

from pathlib import Path

from anytoolai_platform_sdk import ProductBundle


def test_base_bundle_has_no_product_roots() -> None:
    bundle = ProductBundle()

    assert bundle.config_roots() == []
    assert bundle.bundle_id == "base"


class _SamplePackageBundle(ProductBundle):
    """Defined in this test module so `_package_dir()` must resolve to this file's own
    directory, not the caller's current working directory."""

    bundle_id = "sample_package_bundle"

    def config_roots(self) -> list[Path]:
        return [self._package_dir() / "products" / "sample_product"]


def test_package_dir_resolves_to_the_defining_module_not_the_caller_cwd(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    bundle = _SamplePackageBundle()

    this_dir = Path(__file__).resolve().parent
    assert bundle._package_dir() == this_dir
    assert bundle.config_roots() == [this_dir / "products" / "sample_product"]
