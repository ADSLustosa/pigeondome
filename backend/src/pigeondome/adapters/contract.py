"""Tradução de mensagens MQTT (bytes) para o domínio, validando o contrato."""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from pigeondome.domain.models import Detection

MAX_MESSAGE_BYTES = 4096
TOPIC_PATTERN = re.compile(r"^pigeondome/v1/(?P<device>[^/]+)/detections$")
_REPO_CONTRACTS = Path(__file__).resolve().parents[4] / "contracts"


class InvalidMessageError(ValueError):
    """A mensagem recebida não respeita o contrato detection.v1."""


class DetectionParser:
    def __init__(self, contracts_dir: Path | None = None) -> None:
        directory = contracts_dir or Path(
            os.environ.get("PIGEONDOME_CONTRACTS_DIR", str(_REPO_CONTRACTS))
        )
        schema = json.loads((directory / "detection.v1.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self._validator = Draft202012Validator(schema)

    def parse(self, topic: str, raw: bytes) -> Detection:
        """Valida tamanho, JSON, contrato, tópico e regras do domínio, nesta ordem."""
        match = TOPIC_PATTERN.fullmatch(topic)
        if match is None:
            raise InvalidMessageError("tópico inesperado")
        if len(raw) > MAX_MESSAGE_BYTES:
            raise InvalidMessageError("mensagem grande demais")

        try:
            payload: Any = json.loads(raw)
        except (ValueError, RecursionError) as exc:
            raise InvalidMessageError("JSON inválido") from exc

        error = next(self._validator.iter_errors(payload), None)
        if error is not None:
            raise InvalidMessageError(error.message)

        if payload["device_id"] != match.group("device"):
            raise InvalidMessageError("device_id do payload difere do tópico")

        try:
            return Detection(
                device_id=payload["device_id"],
                timestamp=datetime.fromisoformat(payload["timestamp"]),
                pigeon_count=payload["pigeon_count"],
                confidence=float(payload["confidence"]),
            )
        except ValueError as exc:  # inclui InvalidDetectionError
            raise InvalidMessageError(str(exc)) from exc
