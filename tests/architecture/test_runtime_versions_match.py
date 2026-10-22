from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE_MAJOR = (ROOT / ".nvmrc").read_text().strip().removeprefix("v").split(".")[0]
COMPOSE_DIR = ROOT / "infra" / "compose"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
BASE_COMPOSE = COMPOSE_DIR / "docker-compose.yml"
# Every image reference is captured whatever its tag, so floating tags (`lts`, `latest`) or a
# missing tag cannot slip past as "no match".
POSTGRES_IMAGE = re.compile(r"""image:\s*["']?postgres(?::([^\s"']+))?["']?\s*$""", re.MULTILINE)
NODE_IMAGE = re.compile(r"^FROM\s+node(?::(\S+))?", re.MULTILINE)
# Files that must keep pinning PostgreSQL; deleting the image line fails instead of passing.
REQUIRED_POSTGRES_FILES = (
    BASE_COMPOSE,
    COMPOSE_DIR / "docker-compose.agent.yml",
    WORKFLOWS_DIR / "backend.yml",
)
# Staged PostgreSQL 18 rollout (ANY-697): overlays with live data stay on 16 until the revision
# that adds prod-quiesce is deployed; the follow-up that switches them empties this mapping.
STAGED_POSTGRES_MAJORS = {
    "docker-compose.prod.yml": "16",
    "docker-compose.atom-lab.yml": "16",
}


def tag_major(tag: str | None) -> str | None:
    """Return the explicit numeric major of an image tag, or None for floating/missing tags."""
    match = re.match(r"(\d+)(?:[.-]|$)", tag or "")
    return match.group(1) if match else None


@pytest.mark.parametrize(
    ("tag", "major"),
    [
        ("24-slim", "24"),
        ("24.11-slim", "24"),
        ("18", "18"),
        ("18.6-bookworm", "18"),
        ("lts-slim", None),
        ("latest", None),
        ("alpine", None),
        (None, None),
    ],
)
def test_tag_major_rejects_floating_and_missing_tags(tag, major) -> None:
    assert tag_major(tag) == major


def test_image_patterns_capture_unpinned_references() -> None:
    assert NODE_IMAGE.findall("FROM node:24-slim AS build\nFROM node:lts-slim AS runtime\n") == [
        "24-slim",
        "lts-slim",
    ]
    assert POSTGRES_IMAGE.findall("    image: postgres:latest\n    image: postgres\n") == [
        "latest",
        "",
    ]


def test_dockerfile_node_major_matches_nvmrc() -> None:
    dockerfiles = sorted((ROOT / "infra" / "docker").glob("*.Dockerfile"))
    found = {p.name: NODE_IMAGE.findall(p.read_text()) for p in dockerfiles}
    assert any(found.values()), "no node base images found"
    for name, tags in found.items():
        for tag in tags:
            assert tag_major(tag) == NODE_MAJOR, f"{name}: node:{tag} must pin major {NODE_MAJOR}"


def test_postgres_major_matches_base_compose() -> None:
    base_tags = POSTGRES_IMAGE.findall(BASE_COMPOSE.read_text())
    expected = tag_major(base_tags[0]) if base_tags else None
    assert expected, "base compose must pin a numeric postgres major"
    paths = [*COMPOSE_DIR.glob("*.yml"), *WORKFLOWS_DIR.glob("*.yml")]
    found = {p.name: POSTGRES_IMAGE.findall(p.read_text()) for p in paths}
    for path in REQUIRED_POSTGRES_FILES:
        assert found.get(path.name), f"{path.name} must pin a postgres image"
    for name in STAGED_POSTGRES_MAJORS:
        assert found.get(name), f"{name} must pin its staged postgres major"
    for name, tags in found.items():
        want = STAGED_POSTGRES_MAJORS.get(name, expected)
        for tag in tags:
            assert tag_major(tag) == want, f"{name}: postgres:{tag or '<none>'} must pin {want}"
