from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_MAJOR = (ROOT / ".nvmrc").read_text().strip().removeprefix("v").split(".")[0]
BASE_COMPOSE = ROOT / "infra" / "compose" / "docker-compose.yml"
POSTGRES_IMAGE = re.compile(r"image:\s*postgres:(\d+)\b")
NODE_IMAGE = re.compile(r"^FROM\s+node:(\d+)\b", re.MULTILINE)


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
    assert {m for majors in found.values() for m in majors} == {expected.group(1)}, found
