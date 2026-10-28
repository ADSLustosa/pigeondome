# Contratos MQTT

Tudo o que os dispositivos e o backend trocam passa pelo broker Mosquitto, em tópicos versionados, com mensagens JSON validadas por JSON Schema. Os contratos ficam em [`contracts/`](../contracts/) e são a **fonte de verdade**: produtores e consumidores são testados contra os mesmos arquivos.

## Tópicos

Todos começam com `pigeondome/v1/{device_id}/`, onde `v1` é a versão do contrato e `device_id` segue `^[a-z0-9-]{3,32}$`.

| Tópico | Quem publica | QoS | Retain | Contrato |
|---|---|---|---|---|
| `.../detections` | câmera | 1 | não | [`detection.v1`](../contracts/detection.v1.schema.json) |
| `.../status` | câmera (e o broker, na última vontade) | 1 | sim | `{"state": "online" \| "offline"}` |
| `.../commands` | backend (controlador) | 1 | não | [`command.v1`](../contracts/command.v1.schema.json) |
| `.../actuator/state` | atuador (e o broker, na última vontade) | 1 | sim | [`actuator-state.v1`](../contracts/actuator-state.v1.schema.json) |
| `.../actuator/events` | atuador | 1 | não | [`actuator-event.v1`](../contracts/actuator-event.v1.schema.json) |

- **QoS 1** garante entrega, mas pode duplicar. Por isso o ingestor e o controlador gravam de forma idempotente, e o atuador descarta `command_id` repetido.
- **Retain** nos estados faz um assinante novo receber o último estado conhecido na hora.
- **Comandos nunca usam retain**: um comando retido seria reexecutado por quem assinasse depois, e um pulso velho não pode acontecer de novo.

## Permissões por papel

O arquivo [`infra/mosquitto/acl`](../infra/mosquitto/acl) dá a cada papel só o que ele precisa. Não há curingas fora do `+` do `device_id`, nem permissão de leitura e escrita juntas.

| Papel | Lê | Escreve |
|---|---|---|
| `backend` | `detections`, `status`, `actuator/state`, `actuator/events` | `commands` |
| `camera` | nada | `detections`, `status` |
| `actuator` | `commands` | `actuator/state`, `actuator/events` |

Consequências diretas: uma câmera comprometida **não consegue emitir comandos**; um atuador **não consegue ler detecções**; e só o backend pode mandar um pulso.

O broker exige senha (`allow_anonymous false`) e carrega as senhas de `mosquitto/passwd`, gerado por `infra\setup.ps1`. Os testes de `backend/tests/test_mosquitto_acl.py` leem o arquivo de ACL e falham se um papel ganhar permissão a mais.

> [!WARNING]
> O broker escuta em texto simples (`listener 1883`, sem TLS), publicado só em `127.0.0.1` pelo Docker Compose. TLS é pré-requisito antes de qualquer acesso pela rede.

## As mensagens

### Detecção (`detection.v1`)

Contagem de pombos vista por uma câmera. **Só métricas, nunca imagens.**

| Campo | Regra |
|---|---|
| `schema_version` | sempre `1` |
| `device_id` | identificador da câmera |
| `timestamp` | data e hora ISO 8601 |
| `pigeon_count` | inteiro de 0 a 50 |
| `confidence` | número de 0 a 1 |

O esquema recusa campos extras (`additionalProperties: false`).

### Comando (`command.v1`)

| Campo | Regra |
|---|---|
| `command_id` | UUID em minúsculas; identifica o comando e impede execução repetida |
| `action` | `pulse` ou `stop` |
| `duration_s` | de 1 a 10 s; obrigatório em `pulse` e **proibido** em `stop` |
| `issued_at` | instante de emissão, em UTC (sufixo `Z`) |
| `ttl_s` | validade de 1 a 30 s a partir de `issued_at` |
| `reason` | opcional, para auditoria: `trigger` (`detection`, `manual` ou `test`) e `pigeon_count` |

**O contrato não tem campo de potência, tensão ou corrente.** A duração máxima do pulso é a do atuador, e `stop` é sempre aceito.

### Estado do atuador (`actuator-state.v1`)

| Campo | Regra |
|---|---|
| `online` | o atuador está conectado |
| `state` | `safe_off`, `idle`, `pulsing`, `cooldown`, `maintenance` ou `fault` |
| `output_on` | saída energizada; **só pode ser verdadeira em `pulsing`** |
| `last_command_id` | último comando aceito, ou `null` |
| `fault` | `watchdog`, `overcurrent`, `over_budget`, `clock_invalid`, `self_test`, ou `null` |
| `budget_used_s_1h` | segundos com a saída ligada na última hora (0 a 3600) |
| `reported_at` | instante do relato, em UTC |

O esquema impõe as combinações válidas: `online=false` exige `state=safe_off` e `output_on=false`; `output_on=true` exige `state=pulsing`; `state=fault` exige um código em `fault`, e qualquer outro estado exige `null`.

A **última vontade** (LWT) do atuador é uma mensagem de estado já pronta (`online=false`, `safe_off`, saída desligada) que o broker publica se a conexão cair sem despedida. Com o retain, o controlador a recebe mesmo que estivesse desconectado na hora.

### Evento do atuador (`actuator-event.v1`)

Trilha de auditoria de cada comando: `command_accepted`, `command_rejected`, `pulse_started`, `pulse_finished` e `pulse_aborted`.

`reason_code` é **obrigatório** em `command_rejected` e `pulse_aborted`, e **proibido** nos outros. Valores: `expired`, `duplicate`, `busy`, `cooldown`, `budget_exhausted`, `maintenance`, `fault`, `invalid_command`, `stop_command`, `disconnected` e `watchdog`.

O motivo `disconnected` aparece em dois eventos, e o par evento + motivo é inequívoco: em `pulse_aborted`, a conexão caiu durante o pulso; em `command_rejected`, o comando chegou com o atuador desconectado. Quem exibe o motivo deve levar o evento em conta.

## Versionamento (convenção do projeto)

- A versão está no tópico (`v1`) e no campo `schema_version` de cada mensagem.
- Uma mudança que **quebra** quem já usa o contrato (remover ou renomear campo, mudar regra) cria `v2`, com tópicos e esquemas novos, e a `v1` continua funcionando até os dispositivos migrarem.
- Acrescentar um campo opcional não quebra, mas como o esquema recusa campos extras, o consumidor precisa ser atualizado antes do produtor.
