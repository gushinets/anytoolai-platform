"""Offline contract oracle; never imported by runtime or fixture-backed HTTP handlers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/contracts/kernel-capability-manifest/v1"
SCHEMA = ROOT / "docs/generated/capability-manifest-v1.schema.json"
POSITIVE_BYTE_SHA256 = "25f39800090615eeba04cb27ab020332d0cf7cf7250fac6d2e5c38754c89b354"
POSITIVE_VERSION = "sha256:a39bac9f210a6ac67e97e117f8481a5954dc3f36bdaab2fd54c7522b27d6ec29"
DISABLED_VERSION = "sha256:478761c681d02330ed052aabe5e1b472dc1c2ee56d79a568a8009f4b4503a694"
NEGATIVE_CASES = {
    "missing-field": "wire",
    "unknown-field": "wire",
    "unsupported-schema": "wire",
    "boolean-schema-version": "wire",
    "wrong-enabled-type": "wire",
    "invalid-timestamp": "wire",
    "naive-timestamp": "wire",
    "invalid-offset": "wire",
    "duplicate-product": "duplicate_product",
    "duplicate-metric": "duplicate_metric",
    "invalid-reference": "metric_owner",
    "digest-mismatch": "digest",
    "wrong-tenant": "scope",
    "wrong-region": "scope",
}


class ContractFailure(ValueError):
    """Fixed diagnostic categories only; do not expose input payloads."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ContractFailure(code)


def semantic_digest(payload: dict[str, Any]) -> str:
    """Independent of Core projection and anchored by retained literal pins."""
    semantic = {
        key: payload[key]
        for key in ("schema_version", "tenant_id", "region", "products", "usage_metrics")
    }
    semantic["products"] = sorted(semantic["products"], key=lambda row: row["product_id"])
    semantic["usage_metrics"] = sorted(semantic["usage_metrics"], key=lambda row: row["metric_key"])
    canonical = json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_manifest(payload: Any, schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)
    except ValidationError:
        raise ContractFailure("wire") from None
    # JSON Schema's mathematical integer also admits 1.0; the wire protocol requires an int.
    require(type(payload["schema_version"]) is int, "wire")
    # jsonschema's optional date-time dependency is not installed in every check environment.
    timestamp = payload["generated_at"]
    require(
        re.fullmatch(
            r"\d{4}-\d\d-\d\d[Tt]\d\d:\d\d:\d\d(?:\.\d+)?"
            r"(?:[Zz]|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
            timestamp,
        )
        is not None,
        "wire",
    )
    try:
        parsed = datetime.fromisoformat(timestamp.upper().replace("Z", "+00:00"))
    except ValueError:
        raise ContractFailure("wire") from None
    require(parsed.utcoffset() is not None, "wire")
    require((payload["tenant_id"], payload["region"]) == ("anytoolai", "ru"), "scope")
    products = [row["product_id"] for row in payload["products"]]
    metrics = [row["metric_key"] for row in payload["usage_metrics"]]
    require(len(products) == len(set(products)), "duplicate_product")
    require(len(metrics) == len(set(metrics)), "duplicate_metric")
    require(all(row["product_id"] in products for row in payload["usage_metrics"]), "metric_owner")
    require(payload["manifest_version"] == semantic_digest(payload), "digest")


def resolve_schema(value: Any, root: dict[str, Any]) -> Any:
    """Compare wire constraints after resolving the two local reference layouts.

    Pydantic uses $defs, OpenAPI uses components/schemas, and the retained Portal
    schema uses different definition names. Titles/descriptions are documentation.
    """
    if isinstance(value, list):
        return [resolve_schema(item, root) for item in value]
    if not isinstance(value, dict):
        return value
    if "$ref" in value:
        reference = value["$ref"]
        require(reference.startswith("#/"), "nonlocal_reference")
        # Reference siblings are conjunctive constraints, never replacement values.
        # This oracle supports only references plus the annotations/containers it ignores.
        require(
            set(value) <= {"$ref", "$defs", "$schema", "title", "description"},
            "unsupported_reference_siblings",
        )
        target = root
        for part in reference[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return resolve_schema(target, root)
    resolved = {}
    for key, item in value.items():
        if key in {"$defs", "$schema", "title", "description"}:
            continue
        if key == "properties":
            resolved[key] = {name: resolve_schema(field, root) for name, field in item.items()}
        else:
            resolved[key] = resolve_schema(item, root)
    return resolved


def check_fixtures() -> None:
    fixtures = CONTRACT / "fixtures"
    hashes = dict(
        line.split("  ", 1)[::-1]
        for line in (CONTRACT / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    )
    require(set(hashes) == {path.name for path in fixtures.iterdir() if path.is_file()}, "file_set")
    for name, expected in hashes.items():
        require(hashlib.sha256((fixtures / name).read_bytes()).hexdigest() == expected, "byte_hash")
    require(hashes["valid-manifest.json"] == POSITIVE_BYTE_SHA256, "positive_bytes")
    require(
        (fixtures / "valid-manifest.digest").read_text(encoding="utf-8").strip()
        == POSITIVE_VERSION,
        "positive_pin",
    )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    for name, version in (
        ("valid-manifest.json", POSITIVE_VERSION),
        ("default-disabled-manifest.json", DISABLED_VERSION),
    ):
        payload = json.loads((fixtures / name).read_text(encoding="utf-8"))
        validate_manifest(payload, schema)
        require(payload["manifest_version"] == version, "version_pin")
    negative = json.loads((fixtures / "invalid-manifests.json").read_text(encoding="utf-8"))
    require(set(negative) == set(NEGATIVE_CASES), "negative_cases")
    for name, code in NEGATIVE_CASES.items():
        try:
            validate_manifest(negative[name], schema)
        except ContractFailure as error:
            require(str(error) == code, "negative_category")
        else:
            raise ContractFailure("accepted_corruption")


def check_portal_copy(portal_root: Path) -> None:
    peer = portal_root / "docs/contracts/kernel-capability-manifest/v1"
    for name in ("valid-manifest.json", "valid-manifest.digest"):
        require(
            (peer / "fixtures" / name).read_bytes() == (CONTRACT / "fixtures" / name).read_bytes(),
            "portal_fixture_drift",
        )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    peer_schema = json.loads((peer / "manifest.schema.json").read_text(encoding="utf-8"))
    require(
        resolve_schema(schema, schema) == resolve_schema(peer_schema, peer_schema),
        "portal_schema_drift",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portal-root", type=Path, help="Read-only consumer checkout to compare")
    args = parser.parse_args()
    try:
        check_fixtures()
        if args.portal_root is not None:
            check_portal_copy(args.portal_root)
    except (ContractFailure, OSError, ValueError, KeyError):
        print("MANIFEST_ARTIFACT_CONTRACT=FAIL")
        return 1
    print("MANIFEST_ARTIFACT_CONTRACT=PASS")
    if args.portal_root is not None:
        print("PORTAL_ARTIFACT_COPY=PASS")
    print("REAL_HTTP_CONFORMANCE=NOT_RUN_STEP_4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
