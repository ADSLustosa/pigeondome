"""Adaptador PostgreSQL da porta DetectionRepository."""

from datetime import datetime, timedelta
from typing import Any, LiteralString

import psycopg
from psycopg_pool import ConnectionPool

from pigeondome.application.ports import StorageError
from pigeondome.domain.models import Detection, DeviceSummary, SeriesPoint

_INSERT: LiteralString = (
    "INSERT INTO detections (device_id, detected_at, pigeon_count, confidence) "
    "VALUES (%s, %s, %s, %s) "
    "ON CONFLICT (device_id, detected_at) DO NOTHING"
)
_SELECT: LiteralString = (
    "SELECT device_id, detected_at, pigeon_count, confidence FROM detections "
    "WHERE device_id = %s AND detected_at >= %s AND detected_at < %s "
    "ORDER BY detected_at"
)
_DEVICES: LiteralString = (
    "SELECT device_id, count(*), max(detected_at) FROM detections "
    "GROUP BY device_id ORDER BY device_id"
)
# date_bin agrupa em intervalos alinhados à origem (aqui, o início da janela)
_SERIES: LiteralString = (
    "SELECT date_bin(%s, detected_at, %s) AS bucket, "
    "count(*), "
    "count(*) FILTER (WHERE pigeon_count > 0), "
    "avg(pigeon_count)::float8, "
    "max(pigeon_count) "
    "FROM detections "
    "WHERE device_id = %s AND detected_at >= %s AND detected_at < %s "
    "GROUP BY bucket ORDER BY bucket"
)


class PostgresDetectionRepository:
    def __init__(self, pool: ConnectionPool[Any]) -> None:
        self._pool = pool

    def add(self, detection: Detection) -> bool:
        params = (
            detection.device_id,
            detection.timestamp,
            detection.pigeon_count,
            detection.confidence,
        )
        try:
            with self._pool.connection() as conn:
                cursor = conn.execute(_INSERT, params)
                inserted: int = cursor.rowcount
                return inserted == 1
        except psycopg.Error as exc:
            raise StorageError("falha ao gravar a detecção") from exc

    def list_between(self, device_id: str, start: datetime, end: datetime) -> list[Detection]:
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(_SELECT, (device_id, start, end)).fetchall()
        except psycopg.Error as exc:
            raise StorageError("falha ao consultar detecções") from exc
        return [
            Detection(device_id=r[0], timestamp=r[1], pigeon_count=r[2], confidence=r[3])
            for r in rows
        ]

    def list_devices(self) -> list[DeviceSummary]:
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(_DEVICES).fetchall()
        except psycopg.Error as exc:
            raise StorageError("falha ao listar dispositivos") from exc
        return [DeviceSummary(device_id=r[0], readings=r[1], last_detected_at=r[2]) for r in rows]

    def series(
        self, device_id: str, start: datetime, end: datetime, bucket: timedelta
    ) -> list[SeriesPoint]:
        params = (bucket, start, device_id, start, end)
        try:
            with self._pool.connection() as conn:
                rows = conn.execute(_SERIES, params).fetchall()
        except psycopg.Error as exc:
            raise StorageError("falha ao agregar a série temporal") from exc
        return [
            SeriesPoint(
                bucket_start=r[0],
                readings=r[1],
                readings_with_pigeons=r[2],
                mean_pigeons=r[3],
                max_pigeons=r[4],
            )
            for r in rows
        ]
