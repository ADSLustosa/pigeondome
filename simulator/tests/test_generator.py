import json
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from pigeondome_sim.generator import DetectionGenerator

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "detection.v1.schema.json"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

VALID = {
    "schema_version": 1,
    "device_id": "cam-sim-01",
    "timestamp": "2026-10-14T08:00:00+00:00",
    "pigeon_count": 3,
    "confidence": 0.9,
}


def make(seed: int = 42) -> DetectionGenerator:
    return DetectionGenerator("cam-sim-01", random.Random(seed))


def at(hour: int) -> datetime:
    return datetime(2026, 10, 14, hour, 0, tzinfo=UTC)


def test_night_has_no_pigeons() -> None:
    assert all(make(seed).generate(at(3)).pigeon_count == 0 for seed in range(50))


def test_same_seed_gives_same_output() -> None:
    assert make(7).generate(at(8)) == make(7).generate(at(8))


def test_generated_payload_matches_contract() -> None:
    generator = make()
    for hour in range(24):
        VALIDATOR.validate(generator.generate(at(hour)).to_payload())


def test_morning_is_busier_than_midday() -> None:
    generator = make()
    mornings = sum(generator.generate(at(8)).pigeon_count for _ in range(2000))
    middays = sum(generator.generate(at(12)).pigeon_count for _ in range(2000))
    assert mornings > middays


def test_contract_accepts_valid_payload() -> None:
    VALIDATOR.validate(VALID)


@pytest.mark.parametrize(
    "override",
    [
        {"pigeon_count": -1},
        {"pigeon_count": 999},
        {"confidence": 1.5},
        {"device_id": "Cam 01"},
        {"schema_version": 2},
        {"image_base64": "AAAA"},  # privacidade: o contrato proíbe imagens
    ],
)
def test_contract_rejects_invalid_payload(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        VALIDATOR.validate({**VALID, **override})


def test_contract_rejects_missing_field() -> None:
    incomplete = {k: v for k, v in VALID.items() if k != "device_id"}
    with pytest.raises(ValidationError):
        VALIDATOR.validate(incomplete)
