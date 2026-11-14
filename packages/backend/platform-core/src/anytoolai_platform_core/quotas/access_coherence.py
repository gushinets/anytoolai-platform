"""Durable authority serialization. The caller owns the transaction and network I/O."""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from anytoolai_platform_core.quotas.models import ExecutionOwner
from anytoolai_platform_core.storage.db import paid_access_coherence_table as coherence


class AccessCoherenceRepository:
    def __init__(self, session: Session, owner: ExecutionOwner, *, consumer_id: str) -> None:
        self.session = session
        self.owner = owner
        self.consumer_id = consumer_id

    def _scope(self) -> tuple[sa.ColumnElement[bool], ...]:
        return (
            coherence.c.consumer_id == self.consumer_id,
            coherence.c.tenant_id == self.owner.tenant_id,
            coherence.c.region == self.owner.region,
            coherence.c.user_id == self.owner.owner_id,
        )

    def read(self) -> sa.RowMapping | None:
        return (
            self.session.execute(sa.select(coherence).where(*self._scope()))
            .mappings()
            .one_or_none()
        )

    def lock(self) -> sa.RowMapping:
        self.session.execute(
            insert(coherence)
            .values(
                consumer_id=self.consumer_id,
                tenant_id=self.owner.tenant_id,
                region=self.owner.region,
                user_id=self.owner.owner_id,
                revision_floor=0,
            )
            .on_conflict_do_nothing()
        )
        return (
            self.session.execute(sa.select(coherence).where(*self._scope()).with_for_update())
            .mappings()
            .one()
        )

    def invalidate(self, revision: int) -> None:
        row = self.lock()
        floor = max(row["revision_floor"], revision)
        values: dict[str, Any] = {"revision_floor": floor}
        if row["snapshot_revision"] is not None and row["snapshot_revision"] < floor:
            values["snapshot"] = None
        self.session.execute(sa.update(coherence).where(*self._scope()).values(**values))

    def observe_policy(self, revision: int) -> bool:
        row = self.lock()
        if revision < row["policy_floor"]:
            return False
        if revision > row["policy_floor"]:
            self.session.execute(
                sa.update(coherence)
                .where(*self._scope())
                .values(policy_floor=revision, snapshot=None)
            )
        return True

    def evict(self) -> None:
        self.lock()
        self.session.execute(sa.update(coherence).where(*self._scope()).values(snapshot=None))

    def install(
        self, revision: int, policy: int, semantic_digest: str, document: dict[str, Any]
    ) -> None:
        # The owner of installation first locks and validates this row. Keeping the last
        # revision/digest across eviction also prevents same-revision semantic rewrites.
        self.session.execute(
            sa.update(coherence)
            .where(*self._scope())
            .values(
                revision_floor=revision,
                snapshot_revision=revision,
                snapshot_policy_revision=policy,
                semantic_digest=semantic_digest,
                snapshot=document,
            )
        )


def database_wall_time(session: Session) -> datetime:
    return session.execute(sa.select(sa.func.clock_timestamp())).scalar_one()
