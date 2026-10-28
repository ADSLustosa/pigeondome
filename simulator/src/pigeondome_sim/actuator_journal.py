"""Registro de eventos do atuador: a trilha de auditoria que fica NO equipamento.

Os eventos (pulso aceito, iniciado, concluído, interrompido, comando recusado) já saem pelo MQTT,
mas quem os guarda é o controlador. Se a rede, o broker ou o controlador falham, ou se o atuador
reinicia antes de reconectar, o que o equipamento fez some. Aqui cada evento é gravado no próprio
atuador, em disco, independente de rede.

Formato: JSON Lines, um evento por linha, idêntico à mensagem do contrato `actuator-event.v1`
(o mesmo schema valida o arquivo). O arquivo só cresce por acréscimo; ao encher, gira (rotação):

    actuator-<id>-events.jsonl      o atual
    actuator-<id>-events.jsonl.1    o anterior (o mais recente dos antigos)
    ...

Duas regras de segurança valem para qualquer implementação:
- gravar ANTES de ligar a saída: sem registro do pulso, não há pulso;
- se não for possível gravar, o atuador entra em falha e não opera (o desligamento nunca depende
  do registro).

Para ler: python -m pigeondome_sim.actuator_journal <arquivo>
"""

import contextlib
import json
import logging
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("pigeondome_sim.actuator.journal")

SCHEMA_VERSION = 1
DEFAULT_MAX_BYTES = 1_048_576  # 1 MiB por arquivo
DEFAULT_KEEP = 5  # arquivos mantidos (o atual e os antigos): cerca de 5 MiB no total


class JournalError(Exception):
    """O registro não pôde ser gravado."""


@dataclass(frozen=True)
class JournalEntry:
    """Um evento, como o registro o recebe (o núcleo traduz o seu `Event` para isto)."""

    event: str
    command_id: str | None
    at: datetime
    reason: str | None = None


class EventJournal(Protocol):
    def append(self, entries: Sequence[JournalEntry]) -> None:
        """Acrescenta e só retorna depois de gravado em definitivo. Erro: JournalError."""
        ...

    def check(self) -> None:
        """Confirma que dá para gravar (usado no autoteste). Erro: JournalError."""
        ...


class InMemoryEventJournal:
    """Registro que dura só enquanto o processo vive: para testes e para quem não quer arquivo."""

    def __init__(self) -> None:
        self.entries: list[JournalEntry] = []
        self.fail_append: JournalError | None = None
        self.fail_check: JournalError | None = None

    def append(self, entries: Sequence[JournalEntry]) -> None:
        if self.fail_append is not None:
            raise self.fail_append
        self.entries.extend(entries)

    def check(self) -> None:
        if self.fail_check is not None:
            raise self.fail_check


def _iso_utc(moment: datetime) -> str:
    """Mesmo formato do contrato: UTC, milissegundos, sufixo Z."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def encode_line(device_id: str, entry: JournalEntry) -> bytes:
    message: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "device_id": device_id,
        "event": entry.event,
        "command_id": entry.command_id,
        "at": _iso_utc(entry.at),
    }
    if entry.reason is not None:
        message["reason_code"] = entry.reason
    return json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"


class FileEventJournal:
    """Arquivo JSON Lines com `fsync` a cada gravação e rotação por tamanho."""

    def __init__(
        self,
        path: Path,
        device_id: str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        keep: int = DEFAULT_KEEP,
    ) -> None:
        if max_bytes < 1 or keep < 1:
            raise ValueError("max_bytes e keep precisam ser positivos")
        self._path = path
        self._device_id = device_id
        self._max_bytes = max_bytes
        self._keep = keep
        self._tail_checked = False

    def append(self, entries: Sequence[JournalEntry]) -> None:
        if not entries:
            return
        data = b"".join(encode_line(self._device_id, entry) for entry in entries)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._rotate_if_needed(len(data))
            self._terminate_torn_line()
            with self._path.open("ab") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._tail_checked = True
        except OSError as exc:
            self._tail_checked = False  # uma gravação pela metade pode ter deixado meia linha
            log.error("falha ao gravar o registro de eventos (%s): %s", self._path, exc)
            raise JournalError(f"não foi possível gravar {self._path}: {exc}") from exc

    def check(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._terminate_torn_line()
            with self._path.open("ab") as handle:
                handle.flush()
                os.fsync(handle.fileno())
            self._tail_checked = True
        except OSError as exc:
            self._tail_checked = False
            log.error("registro de eventos não está gravável (%s): %s", self._path, exc)
            raise JournalError(f"{self._path} não está gravável: {exc}") from exc

    def _terminate_torn_line(self) -> None:
        """Uma queda no meio da gravação pode deixar meia linha. Fecha-a, para o próximo evento
        não grudar nela: a linha danificada fica isolada e o resto do arquivo continua legível."""
        if self._tail_checked:
            return
        try:
            with self._path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    return
                handle.seek(-1, os.SEEK_END)
                last = handle.read(1)
        except FileNotFoundError:
            return
        if last != b"\n":
            with self._path.open("ab") as handle:
                handle.write(b"\n")
                handle.flush()
                os.fsync(handle.fileno())

    def _rotate_if_needed(self, incoming: int) -> None:
        try:
            size = self._path.stat().st_size
        except FileNotFoundError:
            return
        if size == 0 or size + incoming <= self._max_bytes:
            return
        if self._keep == 1:
            self._path.unlink()
        else:
            # `replace` sobrescreve o destino: o mais antigo é descartado ao ser substituído.
            for number in range(self._keep - 2, 0, -1):
                source = self._numbered(number)
                if source.exists():
                    source.replace(self._numbered(number + 1))
            self._path.replace(self._numbered(1))
        self._tail_checked = True  # o arquivo novo nasce vazio
        self._sync_directory()

    def _numbered(self, number: int) -> Path:
        return self._path.with_name(f"{self._path.name}.{number}")

    def _sync_directory(self) -> None:
        """Garante que as renomeações sobrevivam a uma queda (no Windows não se abre pasta)."""
        if os.name == "nt":
            return
        with contextlib.suppress(OSError):
            fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)


@dataclass
class JournalReading:
    entries: list[dict[str, Any]] = field(default_factory=list)
    damaged_lines: int = 0  # linhas que não são um evento válido (ex.: cortada por uma queda)


def read_journal(path: Path, keep: int = DEFAULT_KEEP) -> JournalReading:
    """Lê do arquivo mais antigo ao mais novo. Linha danificada é contada, sem esconder o resto."""
    reading = JournalReading()
    files = [path.with_name(f"{path.name}.{n}") for n in range(keep - 1, 0, -1)] + [path]
    for file in files:
        try:
            raw = file.read_bytes()
        except FileNotFoundError:
            continue
        for line in raw.split(b"\n"):
            if not line.strip():
                continue
            try:
                item = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                reading.damaged_lines += 1
                continue
            if isinstance(item, dict) and {"event", "at"} <= set(item):
                reading.entries.append(item)
            else:
                reading.damaged_lines += 1
    return reading


def unfinished_pulses(entries: Sequence[dict[str, Any]]) -> list[str]:
    """Comandos com `pulse_started` e sem `pulse_finished`/`pulse_aborted`: queda no meio do pulso.

    Só o último pulso pode estar sem desfecho por queda; os anteriores indicam registro perdido.
    """
    open_ids: dict[str, None] = {}
    for item in entries:
        command_id = str(item.get("command_id"))
        if item.get("event") == "pulse_started":
            open_ids[command_id] = None
        elif item.get("event") in {"pulse_finished", "pulse_aborted"}:
            open_ids.pop(command_id, None)
    return list(open_ids)


def render(reading: JournalReading) -> str:
    lines = [f"{'quando (UTC)':<26}{'evento':<18}{'motivo':<18}comando"]
    for item in reading.entries:
        lines.append(
            f"{str(item['at']):<26}{str(item['event']):<18}"
            f"{str(item.get('reason_code', '')):<18}{str(item.get('command_id') or '')[:8]}"
        )
    for command_id in unfinished_pulses(reading.entries):
        note = "pulso sem desfecho (ainda em curso, ou queda durante o pulso)"
        lines.append(f"! {note}: {command_id[:8]}")
    if reading.damaged_lines:
        lines.append(f"! linhas danificadas: {reading.damaged_lines}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("uso: python -m pigeondome_sim.actuator_journal <arquivo-de-eventos.jsonl>")
        return 2
    path = Path(args[0])
    if not path.exists():
        print(f"arquivo não encontrado: {path}")
        return 1
    print(render(read_journal(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
