"""Independent JSON Schema/semantic oracle for ANY-766 target fixtures only.

No Portal imports, service, storage or credentials. These tests do not implement
the future HTTP routes or prove delivery/transaction behavior.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind, PaidAllowance
from jsonschema import Draft202012Validator, FormatChecker, ValidationError, validators

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "docs/contracts/portal-kernel-paid"
QUANTITY_FIELDS = frozenset({"quantity", "successful_used", "reserved", "remaining", "available"})
TIMESTAMP_FIELDS = frozenset(
    {"refresh_after", "expires_at", "valid_until", "occurred_at", "read_at"}
)
MAX_QUANTITY = 2**53 - 1
CONFLICTING_ALLOWANCE_COUNT = 2
OPERATION_COUNT = 10
STRICT_VALIDATOR = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda _checker, value: type(value) is int
    ),
)


def load(name: str) -> Any:
    return json.loads((CONTRACT / name).read_text(encoding="utf-8"))


VALID = load("fixtures/valid.json") + load("fixtures/backend-valid.json")
INVALID = load("fixtures/invalid.json") + load("fixtures/backend-invalid.json")
CONTEXTUAL = load("fixtures/contextual-invalid.json")


def require(condition: bool, category: str) -> None:
    if not condition:
        raise ValueError(category)


def check_scalar_semantics(value: Any) -> None:
    if isinstance(value, list):
        for row in value:
            check_scalar_semantics(row)
    elif isinstance(value, dict):
        for field, item in value.items():
            if field in TIMESTAMP_FIELDS and item is not None:
                # FormatChecker's optional date-time dependency is not universal.
                require(datetime.fromisoformat(item).utcoffset() == timedelta(0), "UTC timestamp")
            if field in QUANTITY_FIELDS:
                require(type(item) is int and 0 <= item <= MAX_QUANTITY, "strict quantity")
            check_scalar_semantics(item)


def validate_contract(contract: str, payload: dict[str, Any]) -> None:
    schema = load(f"schemas/{contract}.schema.json")
    try:
        STRICT_VALIDATOR(schema, format_checker=FormatChecker()).validate(payload)
    except ValidationError:
        raise ValueError("wire schema") from None
    check_scalar_semantics(payload)
    if contract in {"snapshot-v2", "snapshot-v3"}:
        products = [row["product_id"] for row in payload["grants"]]
        ids = [row["allowance_id"] for row in payload["allowances"]]
        require(len(set(products)) == len(products), "duplicate grant")
        require(len(set(ids)) == len(ids), "duplicate allowance")
        require(
            all(row["product_id"] in products for row in payload["allowances"]), "missing grant"
        )
        require(payload["access_revision"] != 0 or not (products or ids), "nonempty revision zero")
        expires = datetime.fromisoformat(payload["expires_at"])
        require(datetime.fromisoformat(payload["refresh_after"]) <= expires, "refresh ordering")
        for grant in payload["grants"]:
            if grant["valid_until"] is not None:
                require(expires <= datetime.fromisoformat(grant["valid_until"]), "grant deadline")
    if contract in {"usage-response-v1", "cabinet-usage-v1"}:
        ids = [row["allowance_id"] for row in payload["items"]]
        require(len(set(ids)) == len(ids), "duplicate usage item")
        for row in payload["items"]:
            if row["status"] == "observed":
                require(
                    row["remaining"] == max(row["quantity"] - row["successful_used"], 0),
                    "remaining",
                )
                require(
                    row["available"]
                    == max(row["quantity"] - row["successful_used"] - row["reserved"], 0),
                    "available",
                )
                require(row["successful_used"] + row["reserved"] <= row["quantity"], "overdrawn")


def correlate_usage(response: dict[str, Any], query: dict[str, Any]) -> None:
    require(
        all(response[field] == query[field] for field in ("tenant_id", "region", "user_id")),
        "usage owner",
    )
    require(
        [row["allowance_id"] for row in response["items"]] == query["allowance_ids"],
        "usage completeness/order",
    )


def test_schema_inventory_validity_and_retained_bytes() -> None:
    entries = [line.split("  ") for line in (CONTRACT / "SHA256SUMS").read_text().splitlines()]
    paths = [path for _, path in entries]
    actual = {
        path.relative_to(CONTRACT).as_posix()
        for folder in ("schemas", "fixtures")
        for path in (CONTRACT / folder).glob("*.json")
    } | {"contract-index.json"}
    assert len(set(paths)) == len(paths)
    assert set(paths) == actual
    for digest, path in entries:
        assert hashlib.sha256((CONTRACT / path).read_bytes()).hexdigest() == digest, path
    names = set(load("contract-index.json")["schema_owners"])
    assert {row["contract"] for row in VALID} == {row["contract"] for row in INVALID} == names
    schema_names = {
        path.name.removesuffix(".schema.json") for path in (CONTRACT / "schemas").glob("*.json")
    }
    assert schema_names == names
    for name in names:
        Draft202012Validator.check_schema(load(f"schemas/{name}.schema.json"))


@pytest.mark.parametrize("case", VALID, ids=lambda row: row["name"])
def test_positive_target_fixtures(case: dict[str, Any]) -> None:
    validate_contract(case["contract"], case["payload"])


@pytest.mark.parametrize("case", INVALID, ids=lambda row: row["name"])
def test_negative_target_fixtures(case: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_contract(case["contract"], case["payload"])


@pytest.mark.parametrize("case", CONTEXTUAL, ids=lambda row: row["name"])
def test_valid_shape_cannot_override_requested_owner_or_allowances(case: dict[str, Any]) -> None:
    validate_contract("usage-response-v1", case["response"])
    validate_contract("usage-query-v1", case["query"])
    with pytest.raises(ValueError):
        correlate_usage(case["response"], case["query"])


def test_usage_matches_existing_any507_readback_meaning() -> None:
    fixtures = {row["name"]: row["payload"] for row in VALID}
    facts = json.loads((ROOT / "tests/fixtures/execution_metering/readback.json").read_text())
    for name in ("busy", "exhausted"):
        item = fixtures[f"usage-{name}"]["items"][0]
        assert {field: item[field] for field in QUANTITY_FIELDS} == {
            field: facts[name][field] for field in QUANTITY_FIELDS
        }
    assert facts["unobserved"] is None
    assert fixtures["usage-unknown"] == fixtures["usage-foreign"]
    assert set(fixtures["usage-unknown"]["items"][0]) == {"allowance_id", "status"}
    correlate_usage(fixtures["usage-mixed"], fixtures["usage-query"])


def test_snapshot_tuple_is_accepted_by_existing_any507_mechanism() -> None:
    payload = next(row["payload"] for row in VALID if row["name"] == "snapshot-current")
    owner = ExecutionOwner(
        owner_kind=ExecutionOwnerKind.portal_user,
        tenant_id=payload["tenant_id"],
        region=payload["region"],
        owner_id=payload["user_id"],
    )
    allowance = PaidAllowance(owner=owner, **payload["allowances"][0])
    assert allowance.unit == "generation" and allowance.quantity == 1
    assert not hasattr(allowance, "period_start")


def test_duplicate_metric_is_a_local_admission_conflict_not_a_shape_failure() -> None:
    payload = next(
        row["payload"] for row in VALID if row["name"] == "snapshot-metric-local-conflict"
    )
    validate_contract("snapshot-v2", payload)
    pairs = [(row["product_id"], row["metric_key"]) for row in payload["allowances"]]
    assert pairs.count(("proposal_ai", "proposal_ai.generations")) == CONFLICTING_ALLOWANCE_COUNT
    assert pairs.count(("brief_decoder", "brief_decoder.analyses")) == 1


def test_clock_ack_and_exhaustion_specification_vectors() -> None:
    """Offline arithmetic/identity proofs; no durable delivery claim."""
    vectors = load("fixtures/protocol-vectors.json")
    for case in vectors["clock"]:
        now = datetime.fromisoformat(case["now"])
        bounds = [now + timedelta(seconds=300)]
        bounds.extend(datetime.fromisoformat(value) for value in case["deadlines"])
        expiry = min(bounds) - timedelta(seconds=5)
        assert expiry == datetime.fromisoformat(case["expires_at"])
        assert min(now + timedelta(seconds=60), expiry) == datetime.fromisoformat(
            case["refresh_after"]
        )
    for case in vectors["invalidation_ack"]:
        delivered = max(case["sent"], case["delivered_before"])
        assert delivered == case["delivered_after"]
        assert (case["pending"] if case["pending"] > delivered else None) == case["pending_after"]
    for case in vectors["exhaustion_delivery"]:
        validate_contract("exhaustion-v1", case["event"])
        matches = all(case["event"][field] == value for field, value in case["issued"].items())
        assert case["status"] == (204 if matches else 409)
        assert case["new_hint"] == (matches and not case["already_committed"])


def test_operation_ownership_does_not_approve_sales_or_runtime() -> None:
    index = load("contract-index.json")
    assert index["status"] == "TARGET_ONLY"
    assert index["schema_owners"]["snapshot-v2"] == "Portal"
    assert index["schema_owners"]["usage-response-v1"] == "Kernel"
    assert index["schema_owners"]["exhaustion-v1"] == "Kernel"
    assert index["schema_owners"]["exchange-request-v1"] == "Portal"
    operations = {row["path"]: row for row in index["operations"]}
    assert len(operations) == len(index["operations"]) == OPERATION_COUNT
    assert all(row["cache_control"] == "no-store" for row in operations.values())
    assert operations["/internal/v1/access-invalidations"]["permission"] == "access:invalidate"
    assert operations["/internal/v1/usage/{user_id}"]["permission"] == "usage:read"
    assert operations["/v1/portal-session/exchange"]["host"] == "Kernel"


def test_identity_fixtures_bind_pkce_and_utc_expiry_bounds() -> None:
    fixtures = {row["name"]: row["payload"] for row in VALID}
    verifier = fixtures["exchange-request"]["code_verifier"]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
    assert challenge.decode("ascii").rstrip("=") == fixtures["code-request"]["code_challenge"]
    assert fixtures["code-response"]["code"] == fixtures["exchange-request"]["code"]
    issued_at = datetime.fromisoformat("2026-11-09T04:00:00Z")
    assert datetime.fromisoformat(fixtures["code-response"]["expires_at"]) == issued_at + timedelta(
        seconds=60
    )
    expiry = datetime.fromisoformat(fixtures["exchange-response"]["expires_at"])
    assert expiry == issued_at + timedelta(minutes=30)
    assert datetime.fromisoformat(fixtures["introspection-response"]["valid_until"]) == (
        expiry - timedelta(seconds=5)
    )


def test_shape_valid_usage_tuple_mismatch_requires_item_unavailability() -> None:
    owner = next(row["payload"] for row in VALID if row["name"] == "usage-busy")
    for case in load("fixtures/protocol-vectors.json")["usage_tuple"]:
        validate_contract("usage-response-v1", {**owner, "items": [case["item"]]})
        matches = all(case["item"][field] == value for field, value in case["local"].items())
        assert case["cabinet_status"] == ("observed" if matches else "unavailable")


@pytest.mark.parametrize(
    "case", load("fixtures/backend-contextual.json"), ids=lambda row: row["name"]
)
def test_v3_context_requires_consumer_policy_and_immutable_semantics(case: dict[str, Any]) -> None:
    """Specification oracle; no future runtime installer is exercised here."""
    candidate = case["snapshot"]
    validate_contract("snapshot-v3", candidate)
    principal = case["principal"]
    actual_identity = tuple(candidate[field] for field in ("consumer_id", "tenant_id", "region"))
    trusted_identity = tuple(principal[field] for field in ("consumer_id", "tenant_id", "region"))
    refused = (
        actual_identity != trusted_identity or candidate["user_id"] != case["requested_user_id"]
    )
    refused |= "access-snapshot:read" not in principal["permissions"]
    refused |= candidate["consumer_policy_revision"] != principal["consumer_policy_revision"]
    refused |= candidate["consumer_policy_revision"] < case["policy_floor"]
    refused |= candidate["access_revision"] < case["access_floor"]
    refused |= bool(
        {row["product_id"] for row in candidate["grants"]} - set(principal["allowed_products"])
    )
    previous = case["accepted"]
    if previous is not None:
        semantic_key = load("contract-index.json")["identity"]["semantic_key"]
        if all(candidate[field] == previous[field] for field in semantic_key):
            for field, key in (("grants", "product_id"), ("allowances", "allowance_id")):
                refused |= sorted(candidate[field], key=lambda row: row[key]) != sorted(
                    previous[field], key=lambda row: row[key]
                )
    assert case["result"] == ("REFUSE" if refused else "ACCEPT")


def test_consumer_protocol_vectors_are_independent_of_paid_revision_and_other_recipients() -> None:
    vectors = load("fixtures/backend-protocol.json")
    for case in vectors["identity"]:
        principal = case["principal"]
        identity = (principal["consumer_id"], principal["tenant_id"], principal["region"])
        audience = (case["audience"], case["tenant_id"], case["region"])
        permission = "backend-session:" + case["operation"]
        assert case["result"] == (
            "ACCEPT"
            if identity == audience and permission in principal["permissions"]
            else "REFUSE"
        )
    for case in vectors["policies"]:
        for side in ("stored", "configured"):
            policy = {
                key: vectors["principals"][0][key] for key in ("tenant_id", "region", "consumer_id")
            }
            policy["allowed_products"] = sorted(set(case[side + "_products"]))
            encoded = json.dumps(policy, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
            assert (
                case[side + "_digest"]
                == "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            )
        reuse = case["configured_revision"] == case["stored_revision"]
        rollback = case["configured_revision"] < case["stored_revision"]
        conflict = reuse and case["configured_digest"] != case["stored_digest"]
        invalid = type(case["configured_revision"]) is not int or case["configured_revision"] < 1
        assert case["result"] == ("REFUSE" if rollback or conflict or invalid else "ACCEPT")
        assert case["access_revision_after"] == case["access_revision_before"]
    now = datetime.fromisoformat(vectors["now"])
    for case in vectors["filtered_deadlines"]:
        relevant = [
            datetime.fromisoformat(case["deadlines"][product])
            for product in case["allowed_products"]
        ]
        bound = min(now + timedelta(minutes=5), *relevant) - timedelta(seconds=5)
        assert case["status"] == (503 if bound <= now else 200)
        if case["status"] == HTTPStatus.OK:
            assert bound == datetime.fromisoformat(case["expires_at"])
    ack = vectors["recipient_ack"]
    for recipient, old in ack["before"].items():
        after = ack["after"][recipient]
        assert after["pending"] == old["pending"]
        assert after["delivered"] == (
            max(old["delivered"], ack["sent"])
            if recipient == ack["recipient"]
            else old["delivered"]
        )
    synthetic_owner = (
        "synthetic-summary",
        "synthetic_summary",
        "synthetic_summary.results",
        "result",
    )
    for case in vectors["source_ownership"]:
        binding = tuple(case[key] for key in ("consumer_id", "product_id", "metric_key", "unit"))
        assert case["result"] == ("ACCEPT" if binding == synthetic_owner else "REFUSE")


def test_historical_portal_evidence_has_no_new_serialized_owner_or_invented_quantity() -> None:
    """Kernel retains producer-owned history bytes; Portal independently runs its readers."""
    histories = load("fixtures/backend-history.json")
    for case in histories:
        assert hashlib.sha256(case["serialized"].encode()).hexdigest() == case["sha256"]
        document = json.loads(case["serialized"])
        assert "technical_source_id" not in document and "backend_consumer_id" not in document
        assert (
            case["resolved_technical_source_id"]
            == case["resolved_backend_consumer_id"]
            == "platform-kernel"
        )
        if case["name"] == "legacy-purchase-v1-no-quantity":
            assert document["technical_terms"] is None
    purchases = {
        row["name"]: json.loads(row["serialized"]) for row in histories if row["kind"] == "purchase"
    }
    audit = purchases["purchase-v2-full-audit"]
    selected = purchases["purchase-v2-selected"]
    assert audit["technical_terms"] == selected["technical_terms"]
    assert audit["meaning"]["expected_technical_terms_digest"] == audit["technical_terms"]["digest"]
    assert (
        audit["meaning"]["expected_technical_terms_digest"]
        != selected["meaning"]["expected_technical_terms_digest"]
    )


def test_v3_consumer_and_policy_do_not_change_any507_allowance_or_replay_owner() -> None:
    snapshots = [
        row["payload"]
        for row in VALID
        if row["contract"] == "snapshot-v3" and row["payload"]["allowances"]
    ]
    for snapshot in snapshots:
        owner = ExecutionOwner(
            owner_kind=ExecutionOwnerKind.portal_user,
            tenant_id=snapshot["tenant_id"],
            region=snapshot["region"],
            owner_id=snapshot["user_id"],
        )
        allowance = PaidAllowance(owner=owner, **snapshot["allowances"][0])
        assert allowance.owner == owner
        assert not hasattr(owner, "consumer_id") and not hasattr(
            allowance, "consumer_policy_revision"
        )
