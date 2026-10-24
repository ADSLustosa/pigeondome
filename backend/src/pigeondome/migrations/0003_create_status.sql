-- 0003: último estado conhecido do atuador e do controlador, para o painel ler pela API.
-- Uma linha por atuador e uma única linha para o controlador, sobrescritas a cada atualização.
-- Nenhum dado pessoal: só identificadores de dispositivos, estados e instantes.
CREATE TABLE actuator_state (
    actuator_id      text        PRIMARY KEY CHECK (actuator_id ~ '^[a-z0-9-]{3,32}$'),
    online           boolean     NOT NULL,
    -- a lista repete ACTUATOR_STATES (domain/status.py); um teste confere que as duas casam
    state            text        NOT NULL CHECK (
        state IN ('safe_off', 'idle', 'pulsing', 'cooldown', 'maintenance', 'fault')
    ),
    -- campos de exibição: NULL quando o atuador não os relatou de forma válida
    output_on        boolean,
    budget_used_s_1h smallint    CHECK (budget_used_s_1h BETWEEN 0 AND 3600),
    -- hora de RECEPÇÃO, pelo relógio do controlador: a base do "dado desatualizado"
    received_at      timestamptz NOT NULL
);

CREATE TABLE controller_status (
    id           smallint    PRIMARY KEY CHECK (id = 1),
    mode         text        NOT NULL CHECK (mode IN ('off', 'dry_run', 'live', 'experiment')),
    camera_id    text        NOT NULL CHECK (camera_id ~ '^[a-z0-9-]{3,32}$'),
    actuator_id  text        NOT NULL CHECK (actuator_id ~ '^[a-z0-9-]{3,32}$'),
    started_at   timestamptz NOT NULL,
    heartbeat_at timestamptz NOT NULL
);
