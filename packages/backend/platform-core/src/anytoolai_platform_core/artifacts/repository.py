from __future__ import annotations

from dataclasses import asdict

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.storage.db import artifacts_table


def _require_stored_artifact(
    stored: ArtifactRecord | None, record_id: str, operation: str
) -> ArtifactRecord:
    if stored is None:
        raise RuntimeError(f"artifact round-trip failed after {operation}: {record_id}")
    return stored


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, record: ArtifactRecord) -> ArtifactRecord:
        self._session.execute(sa.insert(artifacts_table).values(asdict(record)))
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_artifact(stored, record.id, "create")

    def get(self, artifact_id: str) -> ArtifactRecord | None:
        row = (
            self._session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.id == artifact_id)
            )
            .mappings()
            .one_or_none()
        )
        return None if row is None else ArtifactRecord(**dict(row))

    def update(self, record: ArtifactRecord) -> ArtifactRecord:
        values = asdict(record)
        values.pop("id")
        result = self._session.execute(
            sa.update(artifacts_table).where(artifacts_table.c.id == record.id).values(values)
        )
        if result.rowcount == 0:
            raise LookupError(f"artifact not found: {record.id}")
        self._session.flush()
        stored = self.get(record.id)
        return _require_stored_artifact(stored, record.id, "update")
