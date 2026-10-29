"""Pure, complete capability projection from the validated composed registry."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from anytoolai_platform_core.config.registry import ConfigRegistry


@dataclass(frozen=True)
class CapabilityProduct:
    product_id: str
    enabled: bool


@dataclass(frozen=True)
class CapabilityMetric:
    metric_key: str
    product_id: str
    unit: str
    enabled: bool


@dataclass(frozen=True)
class CapabilityManifest:
    """Manifest semantics only; the HTTP boundary owns generation time and response DTOs."""

    tenant_id: str
    region: str
    products: tuple[CapabilityProduct, ...]
    usage_metrics: tuple[CapabilityMetric, ...]
    schema_version: int = 1

    @property
    def manifest_version(self) -> str:
        semantic = asdict(self)
        semantic["products"] = sorted(semantic["products"], key=lambda item: item["product_id"])
        semantic["usage_metrics"] = sorted(
            semantic["usage_metrics"], key=lambda item: item["metric_key"]
        )
        canonical = json.dumps(
            semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(canonical).hexdigest()


def project_capability_manifest(
    registry: ConfigRegistry, *, tenant_id: str, region: str
) -> CapabilityManifest:
    """Project all registered declarations without consulting runtime state or policy."""
    return CapabilityManifest(
        tenant_id=tenant_id,
        region=region,
        products=tuple(
            CapabilityProduct(product.product_id, product.commercial_admission_enabled)
            for product in sorted(registry.products.values(), key=lambda item: item.product_id)
        ),
        usage_metrics=tuple(
            sorted(
                (
                    CapabilityMetric(
                        metric.metric_key, product.product_id, metric.unit, metric.enabled
                    )
                    for product in registry.products.values()
                    for metric in product.usage_metrics
                ),
                key=lambda item: item.metric_key,
            )
        ),
    )
