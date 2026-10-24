"""Configuração do controlador lida do ambiente (12-Factor App). O padrão é o modo seco."""

import os
from dataclasses import dataclass

from pigeondome.domain.actuation import Mode, PolicyConfig
from pigeondome.domain.models import DEVICE_ID_PATTERN


@dataclass(frozen=True)
class ControllerSettings:
    policy: PolicyConfig
    camera_id: str
    actuator_id: str
    tick_s: float

    @classmethod
    def from_env(cls) -> "ControllerSettings":
        env = os.environ
        try:
            mode = Mode(env.get("CONTROLLER_MODE", Mode.DRY_RUN.value))
        except ValueError as exc:
            raise ValueError("CONTROLLER_MODE deve ser off, dry_run, live ou experiment") from exc
        quiet_start = env.get("CONTROLLER_QUIET_START")
        quiet_end = env.get("CONTROLLER_QUIET_END")
        policy = PolicyConfig(
            mode=mode,
            pulse_s=int(env.get("CONTROLLER_PULSE_S", "5")),
            min_detections=int(env.get("CONTROLLER_MIN_DETECTIONS", "3")),
            retry_gap_s=float(env.get("CONTROLLER_RETRY_GAP_S", "120")),
            max_pulses_per_day=int(env.get("CONTROLLER_MAX_PULSES_PER_DAY", "40")),
            utc_offset_hours=int(env.get("CONTROLLER_UTC_OFFSET_HOURS", "-3")),
            quiet_start_hour=int(quiet_start) if quiet_start else None,
            quiet_end_hour=int(quiet_end) if quiet_end else None,
            experiment_seed=int(env.get("CONTROLLER_EXPERIMENT_SEED", "0")),
        )
        camera_id = env.get("CONTROLLER_CAMERA_ID", "cam-sim-01")
        actuator_id = env.get("CONTROLLER_ACTUATOR_ID", "act-sim-01")
        for name, value in (
            ("CONTROLLER_CAMERA_ID", camera_id),
            ("CONTROLLER_ACTUATOR_ID", actuator_id),
        ):
            if not DEVICE_ID_PATTERN.fullmatch(value):
                raise ValueError(f"{name} inválido: {value!r}")
        tick_s = float(env.get("CONTROLLER_TICK_S", "1"))
        if not 0.2 <= tick_s <= 5:
            raise ValueError("CONTROLLER_TICK_S precisa ficar entre 0,2 e 5 s")
        return cls(policy, camera_id, actuator_id, tick_s)
