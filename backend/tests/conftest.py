import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg_pool import ConnectionPool

from pigeondome.adapters.memory import InMemoryDetectionRepository
from pigeondome.adapters.postgres import PostgresDetectionRepository
from pigeondome.application.ports import DetectionRepository
from pigeondome.migrate import apply_migrations

ENV_VARS = [
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USER",
    "MQTT_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_DB",
    "POSTGRES_PASSWORD",
    "PIGEONDOME_STORAGE",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Testes não podem depender das variáveis de ambiente de quem os executa."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def pg_conninfo() -> Iterator[str]:
    """Conexão a um schema novo e descartável. Sem PIGEONDOME_TEST_DSN, o teste é pulado."""
    dsn = os.environ.get("PIGEONDOME_TEST_DSN")
    if not dsn:
        pytest.skip("defina PIGEONDOME_TEST_DSN para rodar os testes de integração")
    schema = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield make_conninfo(dsn, options=f"-csearch_path={schema}", connect_timeout=5)
    finally:
        with psycopg.connect(dsn, autocommit=True, connect_timeout=5) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.fixture(params=["memory", "postgres"])
def repository(request: pytest.FixtureRequest) -> Iterator[DetectionRepository]:
    """Cada teste que usa esta fixture roda contra os DOIS adaptadores."""
    if request.param == "memory":
        yield InMemoryDetectionRepository()
        return
    conninfo: str = request.getfixturevalue("pg_conninfo")
    apply_migrations(conninfo)
    pool = ConnectionPool(conninfo, min_size=1, max_size=2, open=True)
    try:
        yield PostgresDetectionRepository(pool)
    finally:
        pool.close()
