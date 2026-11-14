"""One immutable consumer owns a database's retained paid execution history."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from anytoolai_platform_core.storage.db import paid_consumer_binding_table as binding


class ConsumerBindingMismatch(ValueError):
    """Configuration cannot reassign existing history to another consumer."""


def check_consumer_binding(session: Session, consumer_id: str) -> bool:
    stored = session.execute(sa.select(binding.c.consumer_id).where(binding.c.id == 1)).scalar()
    if stored is None:
        return False
    if stored != consumer_id:
        raise ConsumerBindingMismatch("Configured Portal consumer does not own this database")
    return True


def require_consumer_binding(session: Session, consumer_id: str) -> None:
    # Existing bindings are never updated, so ordinary requests need no write lock.
    if check_consumer_binding(session, consumer_id):
        return
    session.execute(insert(binding).values(id=1, consumer_id=consumer_id).on_conflict_do_nothing())
    # Concurrent first requests serialize on the singleton key. The loser must
    # check the committed winner before it can observe or write any paid history.
    check_consumer_binding(session, consumer_id)
