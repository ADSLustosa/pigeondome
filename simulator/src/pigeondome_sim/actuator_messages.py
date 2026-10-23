"""Tradução entre o núcleo do atuador e as mensagens JSON dos contratos."""

from datetime import UTC, datetime
from typing import Any

from pigeondome_sim.actuator_core import Action, Command, Event, Snapshot

SCHEMA_VERSION = 1


def iso_utc(moment: datetime) -> str:
    """Instante em UTC, com milissegundos e sufixo Z, como exigem os contratos."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def state_message(device_id: str, snapshot: Snapshot, reported_at: datetime) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "device_id": device_id,
        "online": snapshot.online,
        "state": snapshot.state.value,
        "output_on": snapshot.output_on,
        "last_command_id": snapshot.last_command_id,
        "fault": snapshot.fault.value if snapshot.fault is not None else None,
        "budget_used_s_1h": snapshot.budget_used_s_1h,
        "reported_at": iso_utc(reported_at),
    }


def event_message(device_id: str, event: Event) -> dict[str, Any]:
    message: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "device_id": device_id,
        "event": event.type.value,
        "command_id": event.command_id,
        "at": iso_utc(event.at),
    }
    if event.reason is not None:
        message["reason_code"] = event.reason.value
    return message


def command_from_message(payload: dict[str, Any]) -> Command:
    """Converte uma mensagem JÁ validada contra command.v1 em um comando do núcleo."""
    return Command(
        command_id=payload["command_id"],
        action=Action(payload["action"]),
        issued_at=datetime.fromisoformat(payload["issued_at"]),
        ttl_s=payload["ttl_s"],
        duration_s=payload.get("duration_s"),
    )
