"""The offline paid-recovery renderer pins must match the product-owned backend outputs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PRODUCTS = (
    ROOT / "packages/backend/product-platforms/freelancer-suite/src"
    / "anytoolai_freelancer_suite/products"
)
WEB = ROOT / "apps/web-mirror/src/products"
# These declarative fields are adjacent in each ProductDefinition; missing/reformatted pins
# fail the scenario-set comparison instead of silently escaping the cross-language check.
OUTPUT_CONTRACT = re.compile(
    r'scenarioId:\s*"([^"]+)",\s*'
    r'outputSchema:\s*\{\s*schemaRef:\s*"([^"]+)",\s*schemaVersion:\s*(\d+)\s*\}'
)


@pytest.mark.parametrize(
    ("product", "web_path"),
    [
        ("proposal_ai", "proposalAi/ProposalAIProduct.tsx"),
        ("brief_decoder", "briefDecoder/BriefDecoderProduct.tsx"),
        ("acceptance_builder", "acceptanceBuilder/AcceptanceBuilderProduct.tsx"),
        ("client_update_writer", "clientUpdateWriter/ClientUpdateWriterProduct.tsx"),
        ("task_finder", "taskFinder/TaskFinderProduct.tsx"),
    ],
)
def test_renderer_output_contract_matches_backend(product: str, web_path: str) -> None:
    product_root = PRODUCTS / product
    scenarios = yaml.safe_load((product_root / "scenarios.yaml").read_text())["scenarios"]
    workflows = {
        item["workflow_id"]: item
        for item in yaml.safe_load((product_root / "workflows.yaml").read_text())["workflows"]
    }
    schemas = {
        item["schema_ref"]: item["version"]
        for path in (ROOT / "configs/kernel/schemas.yaml", product_root / "schemas.yaml")
        for item in yaml.safe_load(path.read_text())["schemas"]
    }
    expected = {}
    for scenario in scenarios:
        schema_ref = workflows[scenario["workflow_id"]]["output_schema_ref"]
        expected[scenario["scenario_id"]] = (schema_ref, schemas[schema_ref])
    actual = {
        scenario: (schema, int(version))
        for scenario, schema, version in OUTPUT_CONTRACT.findall((WEB / web_path).read_text())
    }
    assert actual == expected
