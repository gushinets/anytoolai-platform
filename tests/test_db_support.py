from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from tests import db_support


def test_provision_database_attempts_cleanup_when_creation_raises_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintenance_url = make_url("postgresql+psycopg://test:test@localhost:5432/postgres")
    cleaned_names: list[str] = []

    monkeypatch.setattr(
        db_support,
        "require_postgres_test_url",
        lambda _skip_reason: maintenance_url,
    )
    monkeypatch.setattr(
        db_support,
        "create_database",
        lambda _url, _database_name: (_ for _ in ()).throw(RuntimeError("post-create failure")),
    )
    monkeypatch.setattr(
        db_support,
        "drop_database",
        lambda _url, database_name: cleaned_names.append(database_name),
    )

    with pytest.raises(RuntimeError, match="post-create failure"):
        with db_support.provision_database(
            database_name_prefix="anytoolai_test",
            skip_reason="test",
        ):
            pass

    assert len(cleaned_names) == 1
    assert cleaned_names[0].startswith("anytoolai_test_")


def test_provision_database_preserves_setup_error_when_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintenance_url = make_url("postgresql+psycopg://test:test@localhost:5432/postgres")
    monkeypatch.setattr(
        db_support,
        "require_postgres_test_url",
        lambda _skip_reason: maintenance_url,
    )
    monkeypatch.setattr(
        db_support,
        "create_database",
        lambda _url, _database_name: (_ for _ in ()).throw(RuntimeError("setup failure")),
    )
    monkeypatch.setattr(
        db_support,
        "drop_database",
        lambda _url, _database_name: (_ for _ in ()).throw(RuntimeError("cleanup failure")),
    )

    with pytest.raises(RuntimeError, match="setup failure"), db_support.provision_database(
        database_name_prefix="anytoolai_test",
        skip_reason="test",
    ):
        pass
