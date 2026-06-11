"""Composition root for platform runtime and future product bundles."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    loaded_bundles: list[str]


def build_runtime() -> RuntimeBootstrapResult:
    # MVP-A loads platform actions + kernel demo configs only.
    # MVP-B may add FreelancerSuiteBundle here, never inside platform-core.
    return RuntimeBootstrapResult(loaded_bundles=["platform_actions", "kernel_demo"])
