-- 0002: trilha do controlador de atuação (decisões, eventos do atuador e chave geral).
-- Nenhum dado pessoal: só identificadores de dispositivos, contagens e motivos.
CREATE TABLE actuation_decisions (
    decided_at      timestamptz      NOT NULL,
    camera_id       text             NOT NULL CHECK (camera_id ~ '^[a-z0-9-]{3,32}$'),
    actuator_id     text             NOT NULL CHECK (actuator_id ~ '^[a-z0-9-]{3,32}$'),
    mode            text             NOT NULL CHECK (mode IN ('off', 'dry_run', 'live', 'experiment')),
    verdict         text             NOT NULL CHECK (verdict IN ('pulse', 'would_pulse', 'skip')),
    reason          text             NOT NULL,
    detail          text             NOT NULL DEFAULT '',
    arm             text             CHECK (arm IN ('treatment', 'control')),
    duration_s      smallint         CHECK (duration_s BETWEEN 1 AND 10),
    command_id      uuid,
    readings        smallint         NOT NULL CHECK (readings >= 0),
    detections      smallint         NOT NULL CHECK (detections BETWEEN 0 AND readings),
    mean_confidence double precision NOT NULL CHECK (mean_confidence BETWEEN 0 AND 1),
    -- todas as condições foram atendidas (pulso real, modo seco ou controle do experimento)
    triggered       boolean          NOT NULL,
    recorded_at     timestamptz      NOT NULL DEFAULT now(),
    -- a chave primária torna a gravação idempotente
    PRIMARY KEY (actuator_id, camera_id, decided_at)
);

CREATE INDEX actuation_decisions_triggered_idx
    ON actuation_decisions (actuator_id, decided_at) WHERE triggered;

CREATE TABLE actuator_events (
    occurred_at timestamptz NOT NULL,
    actuator_id text        NOT NULL CHECK (actuator_id ~ '^[a-z0-9-]{3,32}$'),
    event       text        NOT NULL CHECK (
        event IN ('command_accepted', 'command_rejected', 'pulse_started',
                  'pulse_finished', 'pulse_aborted')
    ),
    command_id  uuid,
    reason_code text,
    received_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (actuator_id, occurred_at, event)
);

-- Uma única linha (id = 1): a chave geral de desligar o controlador.
CREATE TABLE controller_flags (
    id          smallint    PRIMARY KEY CHECK (id = 1),
    kill_switch boolean     NOT NULL DEFAULT false,
    updated_at  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO controller_flags (id) VALUES (1);
