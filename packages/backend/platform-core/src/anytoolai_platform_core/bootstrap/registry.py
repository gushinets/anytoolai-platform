"""Registry bootstrap helpers."""

from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.config.registry import ConfigRegistry


def default_config_root() -> Path:
    """Return the default repo-local MVP-A config root."""
    return Path(__file__).resolve().parents[6] / "configs" / "kernel"


def build_config_registry(config_root: Path | None = None) -> ConfigRegistry:
    """Load and return the immutable MVP-A config registry."""
    root = config_root or default_config_root()
    return ConfigLoader(root).load()
