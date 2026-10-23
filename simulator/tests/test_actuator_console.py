"""Console do atuador: os comandos que ele monta precisam obedecer ao contrato."""

import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from pigeondome_sim.actuator_console import build_command
from pigeondome_sim.actuator_service import parse_command

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
NOW = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)


def test_built_commands_match_the_contract_and_the_parser() -> None:
    schema = json.loads((CONTRACTS / "command.v1.schema.json").read_text("utf-8"))
    check = Draft202012Validator(schema)
    pulse = build_command("pulse", "act-sim-01", NOW, duration_s=5)
    stop = build_command("stop", "act-sim-01", NOW)
    assert check.is_valid(pulse)
    assert check.is_valid(stop)
    assert "duration_s" not in stop
    assert parse_command(json.dumps(pulse).encode(), "act-sim-01") is not None


def test_each_command_gets_its_own_id() -> None:
    first = build_command("stop", "act-sim-01", NOW)
    second = build_command("stop", "act-sim-01", NOW)
    assert first["command_id"] != second["command_id"]
