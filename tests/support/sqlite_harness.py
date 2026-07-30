from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event


def sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def build_sqlite_runtime_engine(
    main_db: Path,
    platform_db: Path,
    *,
    concurrent_writes: bool = False,
) -> sa.Engine:
    """Build a SQLite engine for the platform's main-db-with-ATTACHed-platform-schema
    layout.

    Shared by every test suite that boots the platform schema on SQLite (directly, or
    transitively -- e.g. test_quota_concurrency_stress.py imports this indirectly via
    test_scenario_runtime_api.py) so this ATTACH wiring lives in one place instead of
    drifting between per-file copies.

    concurrent_writes=True additionally applies the pysqlite SAVEPOINT-under-rollback
    workaround and switches every transaction to BEGIN IMMEDIATE (see below), needed
    by suites that run several read-then-write transactions concurrently and/or rely
    on begin_nested() surviving an outer rollback correctly. Leave it False (the
    default) for suites that intentionally hold multiple concurrent *read-only*
    sessions open at once (e.g. test_quota_service.py's stale-read test): both the
    isolation_level rewrite and BEGIN IMMEDIATE would make even a plain SELECT open an
    explicit transaction/write-reservation immediately, instead of pysqlite's default
    lazy (DML-triggered) implicit BEGIN that those tests depend on.
    """
    engine = sa.create_engine(
        sqlite_url(main_db),
        future=True,
        connect_args={"timeout": 30.0},
    )

    @event.listens_for(engine, "connect")
    def _attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        if concurrent_writes:
            # pysqlite's own implicit-transaction handling fights SQLAlchemy's
            # SAVEPOINT (begin_nested()) support: without disabling it here and
            # re-establishing explicit BEGIN below, a released SAVEPOINT can survive a
            # later rollback of the outer transaction instead of being discarded with
            # it. See
            # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
            dbapi_connection.isolation_level = None
            dbapi_connection.execute("PRAGMA busy_timeout = 30000")
        dbapi_connection.execute(
            "ATTACH DATABASE ? AS platform",
            (platform_db.resolve().as_posix(),),
        )

    if concurrent_writes:

        @event.listens_for(engine, "begin")
        def _begin_transaction(connection: sa.Connection) -> None:
            # IMMEDIATE (not deferred BEGIN) acquires the write-reservation lock at the
            # start of the transaction instead of on first write. With plain BEGIN, two
            # concurrent transactions that both read before they write (e.g. a quota
            # validation SELECT before an INSERT) can each hold a SHARED lock and then
            # deadlock trying to upgrade to a write lock -- a reader-upgrade deadlock
            # that PRAGMA busy_timeout cannot resolve, since neither side will release
            # its shared lock before getting the one it's waiting on. IMMEDIATE makes
            # whichever transaction starts first own the write intent immediately, so
            # everyone else just queues on busy_timeout.
            connection.exec_driver_sql("BEGIN IMMEDIATE")

    return engine
