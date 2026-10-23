"""Console do atuador (ferramenta de desenvolvimento): enviar comandos e acompanhar o estado.

Roda com as credenciais do papel 'backend' (o futuro controlador). Use o script
scripts\actuator-console.ps1, que injeta a senha sem deixá-la na linha de comando.
"""

import argparse
import json
import os
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from pigeondome_sim.actuator_messages import iso_utc
from pigeondome_sim.actuator_service import command_topic, events_topic, state_topic


def build_command(
    action: str,
    device_id: str,
    now: datetime,
    *,
    duration_s: int | None = None,
    ttl_s: int = 10,
    command_id: str | None = None,
) -> dict[str, Any]:
    """Monta uma mensagem de comando que obedece ao contrato command.v1."""
    command: dict[str, Any] = {
        "schema_version": 1,
        "command_id": command_id or str(uuid.uuid4()),
        "device_id": device_id,
        "action": action,
        "issued_at": iso_utc(now),
        "ttl_s": ttl_s,
        "reason": {"trigger": "manual"},
    }
    if duration_s is not None:
        command["duration_s"] = duration_s
    return command


def _connect() -> tuple[mqtt.Client, str]:
    password = os.environ.get("MQTT_PASSWORD", "")
    if not password:
        raise SystemExit("defina MQTT_PASSWORD (use scripts\\actuator-console.ps1)")
    outcome: dict[str, Any] = {}
    ready = threading.Event()

    def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, props: Any) -> None:
        outcome["code"] = reason_code
        ready.set()

    client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"console-{uuid.uuid4().hex[:8]}")
    client.username_pw_set(os.environ.get("MQTT_USER", "backend"), password)
    client.on_connect = on_connect
    client.connect(
        os.environ.get("MQTT_HOST", "127.0.0.1"), int(os.environ.get("MQTT_PORT", "1883")), 15
    )
    client.loop_start()
    if not ready.wait(5) or outcome["code"].is_failure:
        raise SystemExit(f"conexão recusada ou sem resposta: {outcome.get('code')}")
    return client, os.environ.get("ACTUATOR_DEVICE_ID", "act-sim-01")


def _send(action: str, duration_s: int | None) -> int:
    client, device_id = _connect()
    command = build_command(action, device_id, datetime.now(UTC), duration_s=duration_s)
    payload = json.dumps(command, separators=(",", ":"))
    info = client.publish(command_topic(device_id), payload, qos=1)
    info.wait_for_publish(timeout=5)
    print(f"enviado: {payload}")
    client.disconnect()
    client.loop_stop()
    return 0


def _watch() -> int:
    client, device_id = _connect()
    prefix = f"pigeondome/v1/{device_id}/"

    def on_message(_client: Any, _userdata: Any, message: Any) -> None:
        text = message.payload.decode("utf-8", "replace")
        print(f"{datetime.now():%H:%M:%S} {message.topic.removeprefix(prefix)}: {text}", flush=True)

    client.on_message = on_message
    for topic in (state_topic(device_id), events_topic(device_id)):
        client.subscribe(topic, qos=1)
    print("acompanhando o atuador (Ctrl+C para sair)")
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="actuator_console", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pulse = commands.add_parser("pulse", help="envia um pulso")
    pulse.add_argument("--seconds", type=int, default=5, help="duração do pulso (1 a 10)")
    commands.add_parser("stop", help="manda desligar a saída agora")
    commands.add_parser("watch", help="mostra estado e eventos do atuador")
    args = parser.parse_args(argv)
    if args.command == "pulse":
        return _send("pulse", args.seconds)
    if args.command == "stop":
        return _send("stop", None)
    return _watch()


if __name__ == "__main__":
    sys.exit(main())
