import re

import psycopg
import pytest

from pigeondome.migrate import apply_migrations, migration_files


def test_migration_files_are_numbered_sequentially() -> None:
    names = [path.name for path in migration_files()]
    assert names, "nenhuma migração encontrada"
    for expected, name in enumerate(names, start=1):
        assert re.fullmatch(rf"{expected:04d}_[a-z0-9_]+\.sql", name), name


def test_migrations_are_applied_once(pg_conninfo: str) -> None:
    assert apply_migrations(pg_conninfo) == [path.name for path in migration_files()]
    assert apply_migrations(pg_conninfo) == []


def test_database_rejects_invalid_rows(pg_conninfo: str) -> None:
    apply_migrations(pg_conninfo)
    insert = (
        "INSERT INTO detections (device_id, detected_at, pigeon_count, confidence) "
        "VALUES ('cam-sim-01', now(), 99, 0.9)"
    )
    with (
        psycopg.connect(pg_conninfo, autocommit=True) as conn,
        pytest.raises(psycopg.errors.CheckViolation),
    ):
        conn.execute(insert)
