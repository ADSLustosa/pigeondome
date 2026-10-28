"""Memória não volátil do orçamento do atuador.

O orçamento (segundos com a saída ligada na última hora) precisa sobreviver a um reinício, senão
reiniciar o atuador zeraria o limite. O núcleo guarda os pulsos no relógio monotônico, que
recomeça a cada boot; aqui os pulsos são gravados no relógio de parede (UTC), que atravessa
reinícios.

Duas regras de segurança valem para qualquer implementação:
- gravar ANTES de ligar a saída, com o fim PREVISTO do pulso (se o atuador cair no meio, o pulso
  conta inteiro, que é a hipótese conservadora);
- na dúvida (arquivo ilegível ou gravação que falha), o atuador não liga a saída.
"""

import contextlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

log = logging.getLogger("pigeondome_sim.actuator.budget")

FORMAT_VERSION = 1
MAX_RECORDS = 10_000  # muito além do possível (orçamento de 120 s por hora): acima disso, é lixo


class BudgetStoreError(Exception):
    """A memória não pôde ser lida ou gravada."""


class BudgetCorruptError(BudgetStoreError):
    """O conteúdo existe, mas não é confiável."""


@dataclass(frozen=True)
class BudgetRecord:
    """Um pulso: início e fim em UTC. Num pulso em andamento, o fim é o PREVISTO."""

    start: datetime
    end: datetime


class BudgetStore(Protocol):
    def load(self) -> list[BudgetRecord]:
        """Pulsos gravados. Vazio na primeira execução; erro se ilegível ou duvidoso."""
        ...

    def save(self, records: list[BudgetRecord]) -> None:
        """Substitui o conteúdo, de forma atômica: ou tudo, ou nada."""
        ...


class InMemoryBudgetStore:
    """Memória que dura só enquanto o processo vive: para testes e para quem não quer arquivo."""

    def __init__(self, records: list[BudgetRecord] | None = None) -> None:
        self._records = list(records) if records else []
        self.fail_load: BudgetStoreError | None = None
        self.fail_save: BudgetStoreError | None = None
        self.saves = 0

    def load(self) -> list[BudgetRecord]:
        if self.fail_load is not None:
            raise self.fail_load
        return list(self._records)

    def save(self, records: list[BudgetRecord]) -> None:
        if self.fail_save is not None:
            raise self.fail_save
        self._records = list(records)
        self.saves += 1


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("carimbo de tempo não é texto")
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError("carimbo de tempo sem fuso")
    return moment.astimezone(UTC)


def _format_time(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _decode(raw: bytes, device_id: str) -> list[BudgetRecord]:
    """Valida tudo; qualquer dúvida vira ValueError (o chamador trata como arquivo corrompido)."""
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("raiz não é um objeto")
    if data.get("version") != FORMAT_VERSION:
        raise ValueError("versão do formato desconhecida")
    if data.get("device_id") != device_id:
        raise ValueError("arquivo de outro dispositivo")
    pulses = data.get("pulses")
    if not isinstance(pulses, list) or len(pulses) > MAX_RECORDS:
        raise ValueError("lista de pulsos inválida")
    records = []
    for item in pulses:
        if not isinstance(item, dict) or set(item) != {"start", "end"}:
            raise ValueError("pulso fora do formato")
        start, end = _parse_time(item["start"]), _parse_time(item["end"])
        if end < start:
            raise ValueError("pulso termina antes de começar")
        records.append(BudgetRecord(start, end))
    return records


class FileBudgetStore:
    """Arquivo JSON, gravado de forma atômica (arquivo temporário, fsync e renomeação)."""

    def __init__(self, path: Path, device_id: str) -> None:
        self._path = path
        self._device_id = device_id

    def load(self) -> list[BudgetRecord]:
        try:
            raw = self._path.read_bytes()
        except FileNotFoundError:
            return []  # primeira execução
        except OSError as exc:
            log.error("memória do orçamento ilegível (%s): %s", self._path, exc)
            raise BudgetStoreError(f"não foi possível ler {self._path}: {exc}") from exc
        try:
            return _decode(raw, self._device_id)
        except (ValueError, UnicodeDecodeError) as exc:
            log.error("memória do orçamento não é confiável (%s): %s", self._path, exc)
            self._quarantine()
            raise BudgetCorruptError(f"conteúdo de {self._path} não é confiável: {exc}") from exc

    def save(self, records: list[BudgetRecord]) -> None:
        document = {
            "version": FORMAT_VERSION,
            "device_id": self._device_id,
            "pulses": [
                {"start": _format_time(r.start), "end": _format_time(r.end)} for r in records
            ],
        }
        temp = self._path.with_name(self._path.name + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with temp.open("wb") as handle:
                handle.write(json.dumps(document, indent=2).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
            temp.replace(self._path)
            self._sync_directory()
        except OSError as exc:
            log.error("falha ao gravar a memória do orçamento (%s): %s", self._path, exc)
            raise BudgetStoreError(f"não foi possível gravar {self._path}: {exc}") from exc

    def _quarantine(self) -> None:
        """Guarda o arquivo ruim com outro nome, para análise, em vez de apagá-lo."""
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        target = self._path.with_name(f"{self._path.name}.corrupt-{stamp}")
        # O erro principal será levantado de qualquer jeito; sem renomear, o arquivo fica onde está.
        with contextlib.suppress(OSError):
            self._path.replace(target)
            log.error("o arquivo foi guardado à parte, para análise: %s", target)

    def _sync_directory(self) -> None:
        """Garante que a renomeação em si sobreviva a uma queda (no Windows não se abre pasta)."""
        if os.name == "nt":
            return
        with contextlib.suppress(OSError):
            fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
