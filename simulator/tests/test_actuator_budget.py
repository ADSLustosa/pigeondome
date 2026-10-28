"""Memória não volátil do orçamento: o arquivo, e o núcleo que a usa (reinício incluído)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from pigeondome_sim.actuator_budget import (
    BudgetCorruptError,
    BudgetRecord,
    BudgetStoreError,
    FileBudgetStore,
    InMemoryBudgetStore,
)
from pigeondome_sim.actuator_core import (
    Action,
    ActuatorCore,
    Command,
    Event,
    EventType,
    Fault,
    Instant,
    Limits,
    Reason,
    State,
)

BASE = datetime(2026, 10, 23, 12, 0, 0, tzinfo=UTC)
MONO0 = 1000.0
DEVICE = "act-sim-01"


def at(seconds: float, epoch: float = MONO0) -> Instant:
    """O mesmo relógio de parede, e um relógio monotônico que pode ter outra origem (reinício)."""
    return Instant(mono_s=epoch + seconds, wall=BASE + timedelta(seconds=seconds))


def pulse(n: int, *, duration: int = 5, issued: float = 0.0) -> Command:
    return Command(
        command_id=f"00000000-0000-4000-8000-{n:012d}",
        action=Action.PULSE,
        issued_at=BASE + timedelta(seconds=issued),
        ttl_s=30,
        duration_s=duration,
    )


def kinds(events: list[Event]) -> list[EventType]:
    return [event.type for event in events]


def rejection(events: list[Event]) -> Reason | None:
    assert events[-1].type is EventType.COMMAND_REJECTED
    return events[-1].reason


def booted(store: InMemoryBudgetStore, seconds: float = 0.0, epoch: float = MONO0) -> ActuatorCore:
    """Um atuador que acaba de ligar: recupera o orçamento e conecta."""
    core = ActuatorCore(store=store)
    core.restore_budget(at(seconds, epoch))
    core.connection_restored(at(seconds, epoch))
    return core


def advance(core: ActuatorCore, start: float, seconds: int, epoch: float = MONO0) -> None:
    """Deixa o tempo passar de 1 em 1 s, como o laço real (o watchdog é de 5 s)."""
    for step in range(1, seconds + 1):
        core.tick(at(start + step, epoch))


def drain_budget(core: ActuatorCore, start: float = 0.0) -> float:
    """Gasta todo o orçamento (12 pulsos de 10 s, com a pausa entre eles). Devolve o instante."""
    moment = start
    for n in range(1, 13):
        events = core.handle_command(pulse(n, duration=10, issued=moment), at(moment))
        assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_STARTED]
        advance(core, moment, 40)  # 10 s de pulso e 30 s de pausa
        moment += 40
    return moment


# --- o arquivo ------------------------------------------------------------------------------


def records() -> list[BudgetRecord]:
    return [
        BudgetRecord(BASE, BASE + timedelta(seconds=5)),
        BudgetRecord(BASE + timedelta(seconds=40), BASE + timedelta(seconds=47.25)),
    ]


def make_file_store(tmp_path: Path) -> FileBudgetStore:
    return FileBudgetStore(tmp_path / "estado" / f"actuator-{DEVICE}.json", DEVICE)


def test_file_without_previous_run_starts_empty(tmp_path: Path) -> None:
    assert make_file_store(tmp_path).load() == []


def test_file_round_trip_and_atomic_write_leaves_no_temporary(tmp_path: Path) -> None:
    store = make_file_store(tmp_path)
    store.save(records())
    assert store.load() == records()
    assert [path.name for path in (tmp_path / "estado").iterdir()] == [f"actuator-{DEVICE}.json"]


def test_file_is_plain_readable_json_in_utc(tmp_path: Path) -> None:
    store = make_file_store(tmp_path)
    store.save(records())
    data = json.loads((tmp_path / "estado" / f"actuator-{DEVICE}.json").read_text("utf-8"))
    assert data["version"] == 1
    assert data["device_id"] == DEVICE
    assert data["pulses"][0] == {
        "start": "2026-10-23T12:00:00.000000Z",
        "end": "2026-10-23T12:00:05.000000Z",
    }


def valid_document() -> dict[str, object]:
    return {
        "version": 1,
        "device_id": DEVICE,
        "pulses": [
            {"start": "2026-10-23T12:00:00Z", "end": "2026-10-23T12:00:05Z"},
        ],
    }


def with_pulses(pulses: object) -> dict[str, object]:
    return {**valid_document(), "pulses": pulses}


CORRUPT = {
    "lixo": b"isto nao e json",
    "vazio": b"",
    "truncado": json.dumps(valid_document()).encode("utf-8")[:-7],
    "nao_utf8": b"\xff\xfe\x00{",
    "raiz_lista": b"[]",
    "versao_futura": json.dumps({**valid_document(), "version": 2}).encode("utf-8"),
    "outro_dispositivo": json.dumps({**valid_document(), "device_id": "act-sim-02"}).encode(
        "utf-8"
    ),
    "pulsos_nao_e_lista": json.dumps(with_pulses({"a": 1})).encode("utf-8"),
    "fim_antes_do_inicio": json.dumps(
        with_pulses([{"start": "2026-10-23T12:00:05Z", "end": "2026-10-23T12:00:00Z"}])
    ).encode("utf-8"),
    "sem_fuso": json.dumps(
        with_pulses([{"start": "2026-10-23T12:00:00", "end": "2026-10-23T12:00:05"}])
    ).encode("utf-8"),
    "campo_extra": json.dumps(
        with_pulses([{"start": "2026-10-23T12:00:00Z", "end": "2026-10-23T12:00:05Z", "x": 1}])
    ).encode("utf-8"),
    "tempo_nao_e_texto": json.dumps(with_pulses([{"start": 1, "end": 2}])).encode("utf-8"),
    "pulsos_demais": json.dumps(
        with_pulses([{"start": "2026-10-23T12:00:00Z", "end": "2026-10-23T12:00:01Z"}] * 10_001)
    ).encode("utf-8"),
}


@pytest.mark.parametrize("content", CORRUPT.values(), ids=CORRUPT.keys())
def test_untrustworthy_file_is_refused_and_kept_aside_for_analysis(
    tmp_path: Path, content: bytes
) -> None:
    store = make_file_store(tmp_path)
    path = tmp_path / "estado" / f"actuator-{DEVICE}.json"
    path.parent.mkdir()
    path.write_bytes(content)
    with pytest.raises(BudgetCorruptError):
        store.load()
    assert not path.exists()
    kept = list(path.parent.glob(f"{path.name}.corrupt-*"))
    assert len(kept) == 1
    assert kept[0].read_bytes() == content
    assert store.load() == []  # depois de guardado à parte, é como uma primeira execução


def test_unreadable_file_is_an_error_but_not_corruption(tmp_path: Path) -> None:
    path = tmp_path / f"actuator-{DEVICE}.json"
    path.mkdir()  # ler uma pasta como arquivo falha, sem que o conteúdo seja o problema
    with pytest.raises(BudgetStoreError) as raised:
        FileBudgetStore(path, DEVICE).load()
    assert not isinstance(raised.value, BudgetCorruptError)
    assert path.is_dir()


def test_save_failure_is_reported(tmp_path: Path) -> None:
    blocker = tmp_path / "ocupado"
    blocker.write_text("sou um arquivo, nao uma pasta", encoding="utf-8")
    with pytest.raises(BudgetStoreError):
        FileBudgetStore(blocker / "estado.json", DEVICE).save(records())


def test_failed_replace_keeps_the_previous_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = make_file_store(tmp_path)
    store.save(records())

    def refuse(self: Path, target: object) -> Path:
        raise OSError("disco falhou na renomeação")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(BudgetStoreError):
        store.save([])
    monkeypatch.undo()
    assert store.load() == records()  # a gravação interrompida não estraga o que já existia


# --- o núcleo com memória --------------------------------------------------------------------


def test_pulse_is_recorded_before_the_output_turns_on() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    saves_before = store.saves
    core.handle_command(pulse(1, duration=10), at(1))
    assert store.saves == saves_before + 1
    assert store.load() == [BudgetRecord(BASE + timedelta(seconds=1), BASE + timedelta(seconds=11))]
    assert core.output_on


def test_finished_pulse_is_recorded_with_its_real_end() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    core.handle_command(pulse(1, duration=10), at(1))
    core.handle_command(
        Command("00000000-0000-4000-8000-000000000099", Action.STOP, BASE, 5), at(4)
    )  # interrompido aos 3 s de pulso
    assert store.load() == [BudgetRecord(BASE + timedelta(seconds=1), BASE + timedelta(seconds=4))]


def test_restart_does_not_reset_the_budget() -> None:
    store = InMemoryBudgetStore()
    first = booted(store)
    moment = drain_budget(first)

    reborn = booted(store, moment, epoch=77.0)  # outro relógio monotônico, como num novo boot
    assert reborn.budget_used_s(at(moment, 77.0)) == pytest.approx(120.0)
    events = reborn.handle_command(pulse(100, issued=moment), at(moment, 77.0))
    assert rejection(events) is Reason.BUDGET_EXHAUSTED


def test_without_memory_a_restart_does_reset_the_budget() -> None:
    """Contraprova: é exatamente o defeito que a memória corrige."""
    first = ActuatorCore()
    first.connection_restored(at(0))
    moment = drain_budget(first)
    reborn = ActuatorCore()
    reborn.connection_restored(at(moment, 77.0))
    events = reborn.handle_command(pulse(100, issued=moment), at(moment, 77.0))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_STARTED]


def test_restored_budget_ages_out_with_the_window() -> None:
    store = InMemoryBudgetStore()
    moment = drain_budget(booted(store))
    later = moment + 3600
    reborn = booted(store, later, epoch=5.0)
    assert reborn.budget_used_s(at(later, 5.0)) == pytest.approx(0.0)
    events = reborn.handle_command(pulse(100, issued=later), at(later, 5.0))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_STARTED]


def test_a_pulse_cut_short_by_a_crash_counts_in_full() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    core.handle_command(pulse(1, duration=10), at(1))  # cai aos 2 s de pulso: sem fechar o registro
    reborn = booted(store, 3, epoch=500.0)
    assert reborn.budget_used_s(at(3, 500.0)) == pytest.approx(10.0)  # os 10 s previstos, não 2 s


def test_restart_right_after_a_pulse_keeps_the_cooldown() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    core.handle_command(pulse(1, duration=10), at(1))
    reborn = booted(store, 3, epoch=500.0)
    assert reborn.state is State.COOLDOWN
    events = reborn.handle_command(pulse(2, issued=3), at(3, 500.0))
    assert rejection(events) is Reason.COOLDOWN


def test_records_from_the_future_count_in_full() -> None:
    """Relógio de parede que voltou: o orçamento não pode diminuir por causa disso."""
    future = BudgetRecord(BASE + timedelta(hours=5), BASE + timedelta(hours=5, seconds=10))
    store = InMemoryBudgetStore([future])
    reborn = booted(store)
    assert reborn.budget_used_s(at(0)) == pytest.approx(10.0)


def test_old_records_are_dropped_on_restore() -> None:
    old = BudgetRecord(BASE - timedelta(hours=3), BASE - timedelta(hours=3) + timedelta(seconds=10))
    reborn = booted(InMemoryBudgetStore([old]))
    assert reborn.budget_used_s(at(0)) == 0.0
    assert reborn.state is State.IDLE


def test_snapshot_reports_the_restored_budget() -> None:
    store = InMemoryBudgetStore(
        [BudgetRecord(BASE - timedelta(seconds=60), BASE - timedelta(seconds=40))]
    )
    assert booted(store).snapshot(at(0)).budget_used_s_1h == 20


def test_restore_without_memory_does_nothing_and_runs_only_once() -> None:
    core = ActuatorCore()
    core.restore_budget(at(0))
    assert core.snapshot(at(0)).budget_used_s_1h == 0

    store = InMemoryBudgetStore([BudgetRecord(BASE, BASE + timedelta(seconds=10))])
    twice = ActuatorCore(store=store)
    twice.restore_budget(at(0))
    store.fail_load = BudgetCorruptError("não deveria nem ler de novo")
    twice.restore_budget(at(1))
    twice.connection_restored(at(1))
    assert twice.state is State.COOLDOWN  # sem falha: a segunda chamada foi ignorada


# --- na dúvida, a saída fica desligada ------------------------------------------------------


def unreadable_store() -> InMemoryBudgetStore:
    store = InMemoryBudgetStore()
    store.fail_load = BudgetCorruptError("arquivo corrompido")
    return store


def test_unreadable_memory_puts_the_actuator_in_self_test_fault() -> None:
    core = booted(unreadable_store())
    assert core.state is State.FAULT
    assert core.snapshot(at(0)).fault is Fault.SELF_TEST
    events = core.handle_command(pulse(1), at(1))
    assert rejection(events) is Reason.FAULT
    assert not core.output_on


def test_after_unreadable_memory_the_next_hour_counts_as_spent_even_after_reset() -> None:
    store = unreadable_store()
    core = booted(store)
    store.fail_load = None  # o arquivo ruim foi guardado à parte; a memória agora funciona
    core.reset(at(10))
    assert core.state is State.COOLDOWN  # o gasto presumido termina "agora": vale a pausa
    advance(core, 10, 31)
    events = core.handle_command(pulse(1, issued=41), at(41))
    assert rejection(events) is Reason.BUDGET_EXHAUSTED  # sem saber o que foi gasto, nada de pulsos
    advance(core, 41, 3560)
    later = 3601
    events = core.handle_command(pulse(2, issued=later), at(later))
    assert kinds(events) == [EventType.COMMAND_ACCEPTED, EventType.PULSE_STARTED]


def test_a_reset_does_not_clear_the_fault_while_the_memory_still_fails() -> None:
    store = unreadable_store()
    core = booted(store)
    store.fail_save = BudgetStoreError("disco cheio")
    core.reset(at(10))
    assert core.state is State.FAULT
    assert core.snapshot(at(10)).fault is Fault.SELF_TEST


def test_failure_to_record_refuses_the_command_and_the_output_stays_off() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    store.fail_save = BudgetStoreError("disco cheio")
    events = core.handle_command(pulse(1), at(1))
    assert kinds(events) == [EventType.COMMAND_REJECTED]
    assert rejection(events) is Reason.FAULT
    assert not core.output_on
    assert core.state is State.FAULT
    assert core.snapshot(at(1)).fault is Fault.SELF_TEST
    assert core.budget_used_s(at(1)) == 0.0


def test_failure_to_record_at_the_end_of_a_pulse_still_reports_it_and_faults() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    core.handle_command(pulse(1, duration=5), at(1))
    store.fail_save = BudgetStoreError("disco cheio")
    events = core.tick(at(7))
    assert kinds(events) == [EventType.PULSE_FINISHED]
    assert not core.output_on
    assert core.state is State.FAULT


def test_first_connection_checks_that_the_memory_is_writable() -> None:
    store = InMemoryBudgetStore()
    store.fail_save = BudgetStoreError("somente leitura")
    core = ActuatorCore(store=store)
    core.restore_budget(at(0))
    core.connection_restored(at(0))
    assert core.state is State.FAULT
    store.fail_save = None
    core.reset(at(5))
    assert core.state is State.IDLE


def test_restore_applies_the_actuator_own_limits() -> None:
    limits = Limits(cooldown_s=8.0, budget_s=30.0, budget_window_s=300.0)
    store = InMemoryBudgetStore(
        [BudgetRecord(BASE - timedelta(seconds=400), BASE - timedelta(seconds=390))]
    )
    core = ActuatorCore(limits, store)
    core.restore_budget(at(0))
    assert core.budget_used_s(at(0)) == 0.0  # fora da janela de 300 s deste perfil


def test_a_corrupt_file_is_logged_with_where_it_was_kept(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = make_file_store(tmp_path)
    path = tmp_path / "estado" / f"actuator-{DEVICE}.json"
    path.parent.mkdir()
    path.write_text("{isto nao e json", encoding="utf-8")
    with (
        caplog.at_level("ERROR", logger="pigeondome_sim.actuator.budget"),
        pytest.raises(BudgetCorruptError),
    ):
        store.load()
    text = caplog.text
    assert "não é confiável" in text
    assert ".corrupt-" in text


# --- o horário gravado não depende de o relógio de parede concordar com o monotônico ---------


def test_a_restored_pulse_keeps_its_recorded_time_when_the_wall_clock_drifts() -> None:
    original = BudgetRecord(BASE - timedelta(seconds=45), BASE - timedelta(seconds=35))
    store = InMemoryBudgetStore([original])
    core = ActuatorCore(store=store)
    core.restore_budget(Instant(MONO0, BASE))
    # 3 s depois (relógio monotônico), o de parede andou só 0,4 s (ajuste de hora do sistema)
    core.connection_restored(Instant(MONO0 + 3, BASE + timedelta(seconds=0.4)))
    assert store.load() == [original]


def test_older_pulses_keep_their_exact_times_through_later_saves() -> None:
    records = [
        BudgetRecord(BASE - timedelta(seconds=300), BASE - timedelta(seconds=290.123456)),
        BudgetRecord(BASE - timedelta(seconds=100), BASE - timedelta(seconds=94.5)),
    ]
    store = InMemoryBudgetStore(records)
    core = ActuatorCore(store=store)
    core.restore_budget(at(0))
    core.connection_restored(at(1))

    def lagging(seconds: int) -> Instant:  # o relógio de parede atrasa 0,3 s a cada segundo
        return Instant(MONO0 + seconds, BASE + timedelta(seconds=seconds * 0.7))

    core.handle_command(pulse(1, duration=2, issued=2), lagging(2))
    core.tick(lagging(4))  # o pulso termina: nova gravação
    assert store.load()[:2] == records


def test_a_pulse_is_recorded_with_the_wall_time_of_its_acceptance_and_its_real_length() -> None:
    store = InMemoryBudgetStore()
    core = booted(store)
    core.handle_command(pulse(1, duration=10), at(0))
    # o relógio de parede dá um salto de 100 s para a frente enquanto o pulso corre
    core.tick(Instant(MONO0 + 4, BASE + timedelta(seconds=104)))
    stop = Command(
        "00000000-0000-4000-8000-000000000009", Action.STOP, BASE, ttl_s=10, duration_s=None
    )
    core.handle_command(stop, Instant(MONO0 + 4, BASE + timedelta(seconds=104)))
    (record,) = store.load()
    assert record.start == BASE  # a hora de parede de quando o pulso foi aceito
    assert record.end - record.start == timedelta(seconds=4)  # a duração medida pelo monotônico
