-- 0001: leituras de detecção enviadas pelas câmeras (contrato detection.v1).
-- Só contagens: nenhuma imagem e nenhum dado pessoal são armazenados.
CREATE TABLE detections (
    device_id    text             NOT NULL CHECK (device_id ~ '^[a-z0-9-]{3,32}$'),
    detected_at  timestamptz      NOT NULL,
    pigeon_count smallint         NOT NULL CHECK (pigeon_count BETWEEN 0 AND 50),
    confidence   double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    received_at  timestamptz      NOT NULL DEFAULT now(),
    -- a chave primária torna a gravação idempotente (QoS 1 pode duplicar mensagens)
    PRIMARY KEY (device_id, detected_at)
);
