import json
from pathlib import Path

from pigeondome.domain.models import DEVICE_ID_PATTERN, MAX_PIGEONS

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "contracts" / "detection.v1.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_domain_limits_match_contract() -> None:
    props = SCHEMA["properties"]
    assert props["pigeon_count"]["maximum"] == MAX_PIGEONS
    assert props["device_id"]["pattern"] == DEVICE_ID_PATTERN.pattern
