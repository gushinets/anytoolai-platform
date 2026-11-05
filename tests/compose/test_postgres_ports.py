"""Requires Docker Compose CLI; config resolution does not require a Docker daemon."""

import json
import os
import subprocess
from pathlib import Path

import pytest

COMPOSE_DIR = Path(__file__).resolve().parents[2] / "infra" / "compose"
BASE = COMPOSE_DIR / "docker-compose.yml"
DEV = COMPOSE_DIR / "docker-compose.override.yml"
CONFIG_TIMEOUT_SECONDS = 30
POSTGRES_TARGET_PORT = 5432


def resolved_postgres_ports(files: list[Path], overrides: dict[str, str]) -> list[dict]:
    # Ignore operator secrets, .env files and port overrides so the matrix is deterministic.
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("ANYTOOLAI_", "COMPOSE_", "OPENAI_"))
    }
    env.update(
        ANYTOOLAI_POSTGRES_USER="config_test",
        ANYTOOLAI_POSTGRES_PASSWORD="config_test",
        ANYTOOLAI_POSTGRES_DB="config_test",
        ANYTOOLAI_ENABLED_PRODUCT_IDS="kernel_demo",
        ANYTOOLAI_PROD_WORKER_MEMORY_LIMIT="512M",
        ANYTOOLAI_ATOM_LAB_WORKER_MEMORY_LIMIT="512M",
        ANYTOOLAI_ATOM_LAB_ACCESS_CODE="config_test",
        ANYTOOLAI_LIVE_CANARY_TOKEN="config_test",
        OPENAI_API_KEY="config_test",
    )
    env.update(overrides)
    command = ["docker", "compose", "--env-file", os.devnull, "-p", "any730-config-test"]
    for file in files:
        command.extend(["-f", str(file)])
    result = subprocess.run(
        [*command, "config", "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
        timeout=CONFIG_TIMEOUT_SECONDS,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["services"]["postgres"].get("ports", [])


def assert_loopback_publication(ports: list[dict], published: int) -> None:
    assert len(ports) == 1, ports
    assert ports[0]["host_ip"] == "127.0.0.1", ports
    assert int(ports[0]["published"]) == published, ports
    assert ports[0]["target"] == POSTGRES_TARGET_PORT, ports
    assert ports[0]["protocol"] == "tcp", ports


@pytest.mark.parametrize(
    ("files", "overrides", "published"),
    [
        ([BASE, DEV], {}, 5432),
        ([BASE, DEV], {"ANYTOOLAI_POSTGRES_PORT": "15555"}, 15555),
        ([COMPOSE_DIR / "docker-compose.agent.yml"], {}, 55432),
        ([BASE, COMPOSE_DIR / "docker-compose.prod.yml"], {}, None),
        ([BASE, COMPOSE_DIR / "docker-compose.atom-lab.yml"], {}, 5432),
        (
            [BASE, COMPOSE_DIR / "docker-compose.atom-lab.yml"],
            {"ANYTOOLAI_ATOM_LAB_POSTGRES_PORT": "15556"},
            15556,
        ),
    ],
    ids=["dev-default", "dev-override", "agent", "prod", "atom-lab", "atom-lab-override"],
)
def test_effective_postgres_publication(
    files: list[Path], overrides: dict[str, str], published: int | None
) -> None:
    ports = resolved_postgres_ports(files, overrides)
    if published is None:
        assert ports == []
    else:
        assert_loopback_publication(ports, published)


@pytest.mark.parametrize("published", [5432, 15555])
def test_dev_overlay_cannot_add_a_wildcard_publication(tmp_path: Path, published: int) -> None:
    overlay = tmp_path / "unsafe.yml"
    overlay.write_text(
        f'services:\n  postgres:\n    ports:\n      - "{published}:5432"\n',
        encoding="utf-8",
    )
    ports = resolved_postgres_ports(
        [BASE, DEV, overlay], {"ANYTOOLAI_POSTGRES_PORT": str(published)}
    )
    with pytest.raises(AssertionError):
        assert_loopback_publication(ports, published)
