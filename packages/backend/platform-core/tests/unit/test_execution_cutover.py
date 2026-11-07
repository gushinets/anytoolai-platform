from __future__ import annotations

import subprocess

import pytest
import sqlalchemy as sa
from alembic import command
from test_execution_metering_storage import _seed_0015, _snapshot

from scripts.agent import runner
from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.mark.parametrize("drain", [True, False])
def test_quiesce_checks_the_entire_legacy_queue_before_stopping_worker(monkeypatch, capsys, drain):
    with provision_database(
        database_name_prefix="any507_drain",
        upgrade_target="0015",
        skip_reason="execution cutover drain",
    ) as (engine, _, _):
        with engine.begin() as connection:
            old = sa.MetaData(schema="platform")
            old.reflect(connection, schema="platform")
            _seed_0015(connection, old)
        jobs = old.tables["platform.jobs"]
        stops = []
        observed = []

        def query_database(args, **kwargs):
            # Replace only the Compose transport; execute the runner's exact SQL on PostgreSQL.
            with engine.connect() as connection:
                count = connection.scalar(sa.text(args[-1]))
            observed.append(count)
            return subprocess.CompletedProcess(args, 0, stdout=f"{count}\n", stderr="")

        def stop_service(args, env, **kwargs):
            stops.append(args[-1])
            if args[-1] == "platform-worker":
                assert observed[-1] == 0
            return 0

        def count_jobs():
            count = runner._nonterminal_job_count([], {})
            if drain and count:
                # Simulate the old worker completing on another committed connection.
                with engine.begin() as connection:
                    connection.execute(
                        sa.update(jobs)
                        .where(jobs.c.status.in_(["created", "running"]))
                        .values(status="failed")
                    )
            return count

        clock = iter([0.0, 0.0, 0.0, 0.0] if drain else [0.0, 2.0])
        monkeypatch.setattr(runner.subprocess, "run", query_database)
        monkeypatch.setattr(runner, "run_with_env", stop_service)
        monkeypatch.setattr(runner.time, "sleep", lambda _: None)
        monkeypatch.setattr(runner.time, "monotonic", lambda: next(clock))

        result = runner._drain_and_stop_worker([], {}, count_jobs, 1.0, "PROD008")
        assert observed[:1] == [2]  # Created and running jobs in historical scope.
        if drain:
            assert result == 0
            assert observed == [2, 0]
            assert stops == ["platform-api", "platform-worker"]
        else:
            assert result == 1
            assert observed == [2]
            assert stops == ["platform-api"]
            assert "no backup may be taken" in capsys.readouterr().err


def test_failed_0016_migration_rolls_back_ddl_counters_and_version_then_retries():
    with provision_database(
        database_name_prefix="any507_migration_failure",
        upgrade_target="0015",
        skip_reason="execution cutover migration failure",
    ) as (engine, config, _):
        old = sa.MetaData(schema="platform")
        with engine.begin() as connection:
            old.reflect(connection, schema="platform")
            _seed_0015(connection, old)
            before = _snapshot(connection, old)
            columns = {
                col["name"]
                for col in sa.inspect(connection).get_columns(
                    "guest_quota_usage", schema="platform"
                )
            }

        def fail_after_counter_ddl(connection, cursor, statement, parameters, context, many):
            if "CREATE TABLE platform.execution_reservations" in statement:
                raise RuntimeError("injected migration failure")

        sa.event.listen(engine, "before_cursor_execute", fail_after_counter_ddl)
        try:
            with (
                pytest.raises(RuntimeError, match="injected migration failure"),
                engine.begin() as connection,
            ):
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
        finally:
            sa.event.remove(engine, "before_cursor_execute", fail_after_counter_ddl)

        engine.dispose()
        with engine.begin() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0015"
            assert _snapshot(connection, old) == before
            assert {
                col["name"]
                for col in sa.inspect(connection).get_columns(
                    "guest_quota_usage", schema="platform"
                )
            } == columns
            assert not sa.inspect(connection).has_table("paid_allowance_usage", schema="platform")
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert _snapshot(connection, old) == before
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == "0018"


@pytest.mark.parametrize("new_bucket", [False, True])
def test_cutover_classifies_old_admission_after_0016_as_legacy(new_bucket):
    with provision_database(
        database_name_prefix="any507_prepared_cutover",
        upgrade_target="0015",
        skip_reason="prepared guest history cutover",
    ) as (engine, config, _):
        old = sa.MetaData(schema="platform")
        with engine.begin() as connection:
            old.reflect(connection, schema="platform")
            _seed_0015(connection, old)
            config.attributes["connection"] = connection
            command.upgrade(config, "0016")

        # Use only the old schema/writer, including the defaults on a new usage row.
        usage = old.tables["platform.guest_quota_usage"]
        bucket_id = "old_usage_0"
        with engine.begin() as connection:
            if new_bucket:
                previous = dict(
                    connection.execute(sa.select(usage).where(usage.c.id == bucket_id))
                    .mappings()
                    .one()
                )
                bucket_id = "after_preparation"
                connection.execute(
                    usage.insert().values(
                        **{
                            **previous,
                            "id": bucket_id,
                            "period_key": "after_preparation",
                            "used_count": 1,
                        }
                    )
                )
            else:
                connection.execute(
                    usage.update()
                    .where(usage.c.id == bucket_id)
                    .values(used_count=usage.c.used_count + 1)
                )
            before = _snapshot(connection, old)

        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert _snapshot(connection, old) == before
            counters = connection.execute(
                sa.text(
                    "SELECT used_count, legacy_used_count, reserved_count "
                    "FROM platform.guest_quota_usage WHERE id = :id"
                ),
                {"id": bucket_id},
            ).one()
            assert tuple(counters) == (1, 1, 0)
            current = sa.MetaData(schema="platform")
            current.reflect(connection, schema="platform")
            first = _snapshot(connection, current)
            command.upgrade(config, "head")
            assert _snapshot(connection, current) == first
