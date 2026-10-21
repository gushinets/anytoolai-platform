from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_MAJOR = (ROOT / ".nvmrc").read_text().strip().removeprefix("v").split(".")[0]
BASE_COMPOSE = ROOT / "infra" / "compose" / "docker-compose.yml"
POSTGRES_IMAGE = re.compile(r"image:\s*postgres:(\d+)\b")
NODE_IMAGE = re.compile(r"^FROM\s+node:(\d+)\b", re.MULTILINE)
# Staged PostgreSQL 18 rollout (ANY-697): overlays with live data stay on 16 until the revision
# that adds prod-quiesce is deployed; the follow-up that switches them empties this mapping.
STAGED_POSTGRES_MAJORS = {
    "docker-compose.prod.yml": "16",
    "docker-compose.atom-lab.yml": "16",
}


def test_dockerfile_node_major_matches_nvmrc() -> None:
    dockerfiles = sorted((ROOT / "infra" / "docker").glob("*.Dockerfile"))
    found = {p.name: NODE_IMAGE.findall(p.read_text()) for p in dockerfiles}
    assert any(found.values()), "no node base images found"
    assert {n for majors in found.values() for n in majors} <= {NODE_MAJOR}, found


def test_postgres_major_matches_base_compose() -> None:
    expected = POSTGRES_IMAGE.search(BASE_COMPOSE.read_text())
    assert expected, "base compose must pin a postgres major"
    paths = [
        *(ROOT / "infra" / "compose").glob("*.yml"),
        *(ROOT / ".github" / "workflows").glob("*.yml"),
    ]
    found = {p.name: POSTGRES_IMAGE.findall(p.read_text()) for p in paths}
    assert set(STAGED_POSTGRES_MAJORS) <= found.keys(), found
    for name, majors in found.items():
        assert set(majors) <= {STAGED_POSTGRES_MAJORS.get(name, expected.group(1))}, found
    for name in STAGED_POSTGRES_MAJORS:
        assert found[name], f"{name} must pin its staged postgres major"
