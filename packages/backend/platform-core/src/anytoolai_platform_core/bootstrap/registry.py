"""Registry bootstrap helpers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.config.registry import ConfigRegistry


def default_config_root() -> Path:
    """Return the default repo-local MVP-A config root."""
    return Path(__file__).resolve().parents[6] / "configs" / "kernel"


def build_config_registry(
    config_root: Path | None = None,
    *,
    extra_product_roots: Sequence[Path] = (),
) -> ConfigRegistry:
    """Load and return the immutable MVP-A config registry. `extra_product_roots` are
    fully-formed product directories loaded alongside `config_root`'s own products -- the
    application composition root (apps/platform-api/bootstrap.py) passes a ProductBundle's
    resolved config_roots() through here. This function and ConfigLoader stay Path-only and
    ProductBundle-ignorant; platform-core must never import a product bundle package."""
    root = config_root or default_config_root()
    return ConfigLoader(root, extra_product_roots=extra_product_roots).load()
