"""Composition root for platform runtime and future product bundles."""

from dataclasses import dataclass
from pathlib import Path

from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    loaded_bundles: list[str]
    config_registry: ConfigRegistry


def build_runtime(config_root: Path | None = None) -> RuntimeBootstrapResult:
    # MVP-A loads platform actions + kernel demo configs only.
    # MVP-B may add FreelancerSuiteBundle here, never inside platform-core.
    config_registry = build_config_registry(config_root)
    return RuntimeBootstrapResult(
        loaded_bundles=["platform_actions", "kernel_demo"],
        config_registry=config_registry,
    )
