from datetime import UTC, datetime, timedelta

import pytest
from psycopg_pool import ConnectionPool

from pigeondome.adapters.postgres import PostgresDetectionRepository
from pigeondome.application.ports import StorageError
from pigeondome.domain.models import Detection

T0 = datetime(2026, 10, 14, 8, 0, tzinfo=UTC)


def test_driver_errors_are_translated_to_storage_error() -> None:
    # um pool que nunca foi aberto recusa emprestar conexões (sem rede, sem banco)
    pool = ConnectionPool("host=127.0.0.1 port=1 connect_timeout=1", open=False)
    repository = PostgresDetectionRepository(pool)
    with pytest.raises(StorageError):
        repository.add(Detection("cam-sim-01", T0, 1, 0.9))
    with pytest.raises(StorageError):
        repository.list_between("cam-sim-01", T0, T0 + timedelta(hours=1))
