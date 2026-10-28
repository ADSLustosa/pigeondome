"""Registro de eventos do atuador: o arquivo, e o núcleo que o usa (gravar antes de ligar)."""

import json
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from pigeondome_sim import actuator_journal
from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    EventType,
    Fault,
    Reason,
    State,
)
from pigeondome_sim.actuator_journal import (
    FileEventJournal,
    InMemoryEventJournal,
    JournalEntry,
    JournalError,
    read_journal,
    render,
    unfinished_pulses,
)

from .test_actuator_budget import BASE, DEVICE, advance, at, kinds, pulse
from .test_actuator_fuzz import CONTRACTS

EVENT_SCHEMA = Draft202012Validator(
    json.loads((CONTRACTS / "actuator-event.v1.schema.json").read_text("utf-8"))
)
FIRST = "00000000-0000-4000-8000-000000000001"
SECOND = "00000000-0000-4000-8000-000000000002"


def entry(
    name: str = "pulse_started", command_id: str | None = FIRST, reason: str | None = None
) -> JournalEntry:
    return JournalEntry(name, command_id, BASE, reason)


def lines(path: Path) -> list[bytes]:
    return path.read_bytes().splitlines()


# --- o arquivo ------------------------------------------------------------------------------


def test_each_entry_is_one_line_that_follows_the_event_contract(tmp_path: Path) -> None:
    journal = FileEventJournal(tmp_path / "events.jsonl", DEVICE)
    journal.append(
        [
            entry("command_accepted", reason=None),
            entry("pulse_started"),
            entry("pulse_aborted", reason="disconnected"),
            entry("command_rejected", command_id=None, reason="invalid_command"),
        ]
    )
    written = lines(tmp_path / "events.jsonl")
    assert len(written) == 4
    for line in written:
        EVENT_SCHEMA.validate(json.loads(line))
    assert b"reason_code" not in written[0]
    assert json.loads(written[2])["reason_code"] == "disconnected"
    assert json.loads(written[3])["command_id"] is None
    assert json.loads(written[0])["at"] == "2026-10-23T12:00:00.000Z"


def test_the_file_only_grows_and_survives_a_new_instance(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    FileEventJournal(path, DEVICE).append([entry("command_accepted")])
    FileEventJournal(path, DEVICE).append([entry("pulse_started")])  # outro boot
    names = [json.loads(line)["event"] for line in lines(path)]
    assert names == ["command_accepted", "pulse_started"]


def test_appending_nothing_creates_nothing(tmp_path: Path) -> None:
    FileEventJournal(tmp_path / "events.jsonl", DEVICE).append([])
    assert list(tmp_path.iterdir()) == []


def test_the_folder_is_created_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "a" / "b" / "events.jsonl"
    FileEventJournal(path, DEVICE).append([entry()])
    assert path.exists()


def test_a_full_file_rotates_and_the_oldest_is_dropped(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = FileEventJournal(path, DEVICE, max_bytes=300, keep=3)
    for n in range(1, 13):
        journal.append([entry(command_id=f"00000000-0000-4000-8000-{n:012d}")])
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "events.jsonl",
        "events.jsonl.1",
        "events.jsonl.2",
    ]
    assert all(p.stat().st_size <= 300 for p in tmp_path.iterdir())
    reading = read_journal(path, keep=3)
    ids = [item["command_id"][-2:] for item in reading.entries]
    assert ids == sorted(ids)  # do mais antigo ao mais novo
    assert ids[-1] == "12"  # o mais novo está lá
    assert "01" not in ids  # o mais antigo foi descartado
    assert reading.damaged_lines == 0


def test_with_keep_one_the_full_file_is_replaced(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = FileEventJournal(path, DEVICE, max_bytes=200, keep=1)
    for _ in range(6):
        journal.append([entry()])
    assert [p.name for p in tmp_path.iterdir()] == ["events.jsonl"]
    assert 0 < path.stat().st_size <= 200


def test_an_entry_bigger_than_the_limit_is_still_recorded(tmp_path: Path) -> None:
    journal = FileEventJournal(tmp_path / "events.jsonl", DEVICE, max_bytes=10, keep=2)
    journal.append([entry()])
    journal.append([entry("pulse_finished")])
    assert len(read_journal(tmp_path / "events.jsonl", keep=2).entries) == 2


def test_invalid_sizes_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positivos"):
        FileEventJournal(tmp_path / "e.jsonl", DEVICE, max_bytes=0)
    with pytest.raises(ValueError, match="positivos"):
        FileEventJournal(tmp_path / "e.jsonl", DEVICE, keep=0)


def test_a_line_cut_by_a_power_failure_does_not_swallow_the_next_event(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    FileEventJournal(path, DEVICE).append([entry("command_accepted")])
    with path.open("ab") as handle:
        handle.write(b'{"schema_version":1,"device_id":"act-si')  # queda no meio da gravação
    FileEventJournal(path, DEVICE).append([entry("pulse_started")])  # outro boot
    reading = read_journal(path)
    assert [item["event"] for item in reading.entries] == ["command_accepted", "pulse_started"]
    assert reading.damaged_lines == 1  # a meia linha fica isolada e contada


def test_check_confirms_the_file_is_writable_without_adding_events(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    FileEventJournal(path, DEVICE).check()
    assert path.exists()
    assert path.stat().st_size == 0


def test_check_also_closes_a_torn_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_bytes(b'{"event":"pulse_sta')
    journal = FileEventJournal(path, DEVICE)
    journal.check()
    journal.append([entry("pulse_finished")])
    assert read_journal(path).damaged_lines == 1
    assert len(read_journal(path).entries) == 1


def test_a_failure_to_write_is_reported_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("é um arquivo", encoding="utf-8")
    journal = FileEventJournal(blocker / "events.jsonl", DEVICE)
    with pytest.raises(JournalError):
        journal.append([entry()])
    with pytest.raises(JournalError):
        journal.check()
    assert "falha ao gravar o registro" in caplog.text
    assert "não está gravável" in caplog.text


def test_a_failed_rotation_is_a_journal_error(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = FileEventJournal(path, DEVICE, max_bytes=50, keep=2)
    journal.append([entry()])
    (tmp_path / "events.jsonl.1").mkdir()  # no caminho da renomeação
    with pytest.raises(JournalError):
        journal.append([entry()])


def test_a_directory_in_place_of_the_file_is_a_journal_error(tmp_path: Path) -> None:
    (tmp_path / "events.jsonl").mkdir()
    with pytest.raises(JournalError):
        FileEventJournal(tmp_path / "events.jsonl", DEVICE).append([entry()])


def test_the_in_memory_journal_records_and_can_be_made_to_fail() -> None:
    journal = InMemoryEventJournal()
    journal.append([entry(), entry("pulse_finished")])
    assert [e.event for e in journal.entries] == ["pulse_started", "pulse_finished"]
    journal.fail_append = JournalError("disco cheio")
    journal.fail_check = JournalError("disco cheio")
    with pytest.raises(JournalError):
        journal.append([entry()])
    with pytest.raises(JournalError):
        journal.check()
    assert len(journal.entries) == 2


# --- leitura --------------------------------------------------------------------------------


def test_reading_counts_damaged_lines_and_keeps_the_rest(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    good = json.dumps({"event": "pulse_started", "at": "x", "command_id": FIRST})
    path.write_bytes(
        b"lixo\n" + good.encode() + b"\n\n[1,2]\n" + b"\xff\xfe\n" + b'{"semevento":1}\n'
    )
    reading = read_journal(path)
    assert len(reading.entries) == 1
    assert reading.damaged_lines == 4


def test_reading_a_missing_file_is_empty(tmp_path: Path) -> None:
    reading = read_journal(tmp_path / "nao-existe.jsonl")
    assert (reading.entries, reading.damaged_lines) == ([], 0)


def test_unfinished_pulses_flags_a_pulse_without_an_outcome() -> None:
    items: list[dict[str, Any]] = [
        {"event": "pulse_started", "command_id": FIRST},
        {"event": "pulse_finished", "command_id": FIRST},
        {"event": "pulse_started", "command_id": SECOND},
    ]
    assert unfinished_pulses(items) == [SECOND]
    items.append({"event": "pulse_aborted", "command_id": SECOND})
    assert unfinished_pulses(items) == []


def test_render_shows_the_table_and_the_warnings(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    journal = FileEventJournal(path, DEVICE)
    journal.append([entry("command_rejected", reason="busy"), entry("pulse_started")])
    with path.open("ab") as handle:
        handle.write(b"meia linha")
    text = render(read_journal(path))
    assert "command_rejected" in text
    assert "busy" in text
    assert "pulso sem desfecho" in text
    assert "linhas danificadas: 1" in text


def test_the_command_line_reader(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "events.jsonl"
    FileEventJournal(path, DEVICE).append([entry("pulse_finished")])
    assert actuator_journal.main([str(path)]) == 0
    assert "pulse_finished" in capsys.readouterr().out
    assert actuator_journal.main([str(tmp_path / "nao-existe.jsonl")]) == 1
    assert "não encontrado" in capsys.readouterr().out
    assert actuator_journal.main([]) == 2
    assert "uso:" in capsys.readouterr().out


def test_the_command_line_reader_uses_the_process_arguments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["actuator_journal"])
    assert actuator_journal.main() == 2
    assert "uso:" in capsys.readouterr().out


# --- o núcleo -------------------------------------------------------------------------------


def core_with(journal: InMemoryEventJournal | None = None) -> tuple[ActuatorCore, Any]:
    journal = journal if journal is not None else InMemoryEventJournal()
    core = ActuatorCore(journal=journal)
    core.connection_restored(at(0))
    return core, journal


def names(journal: InMemoryEventJournal) -> list[str]:
    return [e.event for e in journal.entries]


def test_a_whole_pulse_is_recorded_in_order() -> None:
    core, journal = core_with()
    returned = core.handle_command(pulse(1, duration=5), at(0))
    returned += core.tick(at(5))
    assert names(journal) == [e.type.value for e in returned]
    assert names(journal) == ["command_accepted", "pulse_started", "pulse_finished"]
    assert all(e.command_id == pulse(1).command_id for e in journal.entries)


def test_the_journal_is_written_before_the_output_turns_on() -> None:
    seen: list[bool] = []

    class Spy(InMemoryEventJournal):
        def append(self, entries: Any) -> None:
            seen.append(core.output_on)
            super().append(entries)

    core = ActuatorCore(journal=Spy())
    core.connection_restored(at(0))
    core.handle_command(pulse(1), at(0))
    assert seen[0] is False  # ao gravar aceitação e início, a saída ainda estava desligada
    assert core.output_on is True


def test_rejections_are_recorded_with_their_reason() -> None:
    core, journal = core_with()
    core.handle_command(pulse(1), at(0))
    core.handle_command(pulse(2), at(1))  # ocupado
    core.reject_invalid(at(2), None)
    reasons = [(e.event, e.reason) for e in journal.entries if e.event == "command_rejected"]
    assert reasons == [("command_rejected", "busy"), ("command_rejected", "invalid_command")]


def test_stop_and_the_abort_it_causes_are_recorded() -> None:
    core, journal = core_with()
    core.handle_command(pulse(1, duration=10), at(0))
    stop = Command(
        "00000000-0000-4000-8000-000000000009", Action.STOP, BASE, ttl_s=10, duration_s=None
    )
    core.handle_command(stop, at(3))
    assert names(journal)[-2:] == ["command_accepted", "pulse_aborted"]
    assert journal.entries[-1].reason == Reason.STOP_COMMAND.value


def test_events_that_happen_offline_are_recorded_at_once() -> None:
    core, journal = core_with()
    core.handle_command(pulse(1, duration=10), at(0))
    core.connection_lost(at(4))  # a rede caiu: nada vai ao MQTT, mas o registro tem o evento
    assert journal.entries[-1].event == "pulse_aborted"
    assert journal.entries[-1].reason == Reason.DISCONNECTED.value


def test_the_watchdog_abort_is_recorded() -> None:
    core, journal = core_with()
    core.handle_command(pulse(1, duration=10), at(0))
    core.tick(at(20))  # ninguém chamou tick por mais de 5 s
    assert journal.entries[-1].event == "pulse_aborted"
    assert journal.entries[-1].reason == Reason.WATCHDOG.value


def test_without_a_journal_nothing_changes() -> None:
    core = ActuatorCore()
    core.connection_restored(at(0))
    assert kinds(core.handle_command(pulse(1), at(0))) == [
        EventType.COMMAND_ACCEPTED,
        EventType.PULSE_STARTED,
    ]


def test_if_the_journal_cannot_be_written_the_pulse_never_starts() -> None:
    journal = InMemoryEventJournal()
    core, _ = core_with(journal)
    journal.fail_append = JournalError("disco cheio")
    events = core.handle_command(pulse(1), at(0))
    assert kinds(events) == [EventType.COMMAND_REJECTED]
    assert events[0].reason is Reason.FAULT
    assert core.output_on is False
    snapshot = core.snapshot(at(0))
    assert (snapshot.state, snapshot.fault) == (State.FAULT, Fault.SELF_TEST)
    assert snapshot.budget_used_s_1h == 0  # o pulso previsto não ficou contando como ativo


def test_a_journal_that_fails_mid_pulse_still_lets_the_output_turn_off() -> None:
    journal = InMemoryEventJournal()
    core, _ = core_with(journal)
    core.handle_command(pulse(1, duration=5), at(0))
    journal.fail_append = JournalError("disco cheio")
    events = core.tick(at(5))  # o fim do pulso não pôde ser registrado
    assert kinds(events) == [EventType.PULSE_FINISHED]
    assert core.output_on is False  # desligar nunca depende do registro
    assert core.snapshot(at(5)).fault is Fault.SELF_TEST


def test_stop_works_even_if_the_journal_is_broken() -> None:
    journal = InMemoryEventJournal()
    core, _ = core_with(journal)
    core.handle_command(pulse(1, duration=10), at(0))
    journal.fail_append = JournalError("disco cheio")
    stop = Command(
        "00000000-0000-4000-8000-000000000009", Action.STOP, BASE, ttl_s=10, duration_s=None
    )
    events = core.handle_command(stop, at(2))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_ABORTED]
    assert core.output_on is False


def test_a_broken_journal_keeps_new_pulses_blocked_until_the_local_reset() -> None:
    journal = InMemoryEventJournal()
    core, _ = core_with(journal)
    journal.fail_append = JournalError("disco cheio")
    core.handle_command(pulse(1), at(0))
    journal.fail_append = None
    journal.fail_check = JournalError("ainda sem espaço")
    advance(core, 0, 40)
    blocked = core.handle_command(pulse(2, issued=40), at(40))
    assert blocked[-1].reason is Reason.FAULT
    core.reset(at(41))  # o reset refaz o autoteste, que confere o registro
    assert core.snapshot(at(41)).fault is Fault.SELF_TEST
    journal.fail_check = None
    core.reset(at(42))
    assert core.snapshot(at(42)).state is State.IDLE
    assert kinds(core.handle_command(pulse(3, issued=42), at(42))) == [
        EventType.COMMAND_ACCEPTED,
        EventType.PULSE_STARTED,
    ]


def test_the_first_connection_checks_that_the_journal_is_writable() -> None:
    journal = InMemoryEventJournal()
    journal.fail_check = JournalError("somente leitura")
    core = ActuatorCore(journal=journal)
    core.connection_restored(at(0))
    snapshot = core.snapshot(at(0))
    assert (snapshot.state, snapshot.fault) == (State.FAULT, Fault.SELF_TEST)


def test_the_stored_events_match_what_a_real_file_holds(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    core = ActuatorCore(journal=FileEventJournal(path, DEVICE))
    core.connection_restored(at(0))
    core.handle_command(pulse(1, duration=5), at(0))
    core.tick(at(5))
    stored = [json.loads(line) for line in lines(path)]
    for item in stored:
        EVENT_SCHEMA.validate(item)
    assert [item["event"] for item in stored] == [
        "command_accepted",
        "pulse_started",
        "pulse_finished",
    ]
    assert stored[-1]["at"] == (BASE + timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def test_concurrent_writers_never_interleave_inside_a_line(tmp_path: Path) -> None:
    """O runner usa um lock; aqui conferimos que cada gravação é uma linha inteira."""
    path = tmp_path / "events.jsonl"
    journal = FileEventJournal(path, DEVICE)
    lock = threading.Lock()

    def work(n: int) -> None:
        for _ in range(20):
            with lock:
                journal.append([entry(command_id=f"00000000-0000-4000-8000-{n:012d}")])

    threads = [threading.Thread(target=work, args=(n,)) for n in range(1, 5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    reading = read_journal(path)
    assert (len(reading.entries), reading.damaged_lines) == (80, 0)
