# Contratos

JSON Schemas das mensagens MQTT. São a **fonte de verdade**: o backend e o simulador são testados contra estes mesmos arquivos.

| Arquivo | Mensagem |
|---|---|
| [`detection.v1.schema.json`](detection.v1.schema.json) | Contagem de pombos de uma câmera |
| [`command.v1.schema.json`](command.v1.schema.json) | Comando ao atuador (`pulse` ou `stop`) |
| [`actuator-state.v1.schema.json`](actuator-state.v1.schema.json) | Estado do atuador |
| [`actuator-event.v1.schema.json`](actuator-event.v1.schema.json) | Evento do atuador |

Os esquemas recusam campos extras. Uma mudança que quebra quem já usa o contrato cria `v2`, em vez de alterar a `v1`. Tópicos, permissões, QoS e regras: [Contratos MQTT](../docs/contratos-mqtt.md).
