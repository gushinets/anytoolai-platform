from pathlib import Path

import pytest
import yaml

COMPOSE_DIR = Path(__file__).resolve().parents[2] / "infra" / "compose"


@pytest.mark.parametrize(
    ("filename", "publication"),
    [
        ("docker-compose.yml", "127.0.0.1:${ANYTOOLAI_POSTGRES_PORT:-5432}:5432"),
        ("docker-compose.agent.yml", "127.0.0.1:55432:5432"),
    ],
)
def test_local_postgres_publication_is_loopback_only(filename: str, publication: str) -> None:
    compose = yaml.safe_load((COMPOSE_DIR / filename).read_text(encoding="utf-8"))
    assert compose["services"]["postgres"]["ports"] == [publication]
