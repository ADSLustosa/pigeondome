"""Servidor HTTP da API de leitura. Uso: python -m pigeondome.api_server"""

import logging
import sys

import psycopg
import uvicorn
from psycopg_pool import ConnectionPool

from pigeondome.adapters.api.actuation_routes import ActuationPorts
from pigeondome.adapters.api.app import create_app
from pigeondome.adapters.postgres import PostgresDetectionRepository
from pigeondome.adapters.postgres_actuation import (
    PostgresActuatorEventRepository,
    PostgresControllerFlags,
    PostgresDecisionRepository,
)
from pigeondome.adapters.postgres_status import (
    PostgresActuatorStateRepository,
    PostgresControllerStatusRepository,
)
from pigeondome.config import ApiSettings, DatabaseSettings
from pigeondome.migrate import apply_migrations

log = logging.getLogger("pigeondome")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        api = ApiSettings.from_env()
        db = DatabaseSettings.from_env()
    except ValueError as exc:
        log.error("configuração inválida: %s", exc)
        return 2

    try:
        # idempotente e protegido por trava: pode rodar junto com o ingestor
        apply_migrations(db.conninfo)
        pool = ConnectionPool(db.conninfo, min_size=1, max_size=4, open=True)
        try:
            pool.wait(timeout=10)
            ports = ActuationPorts(
                actuators=PostgresActuatorStateRepository(pool),
                controller=PostgresControllerStatusRepository(pool),
                decisions=PostgresDecisionRepository(pool),
                events=PostgresActuatorEventRepository(pool),
                flags=PostgresControllerFlags(pool),
            )
            app = create_app(PostgresDetectionRepository(pool), api.allowed_origins, ports)
            uvicorn.run(app, host=api.host, port=api.port, log_level="info")
        finally:
            pool.close()
    except psycopg.Error as exc:
        log.error("banco de dados indisponível: %s", exc)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
