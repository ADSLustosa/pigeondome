# API

API REST de **leitura**, com uma única ação de escrita (ligar a chave geral). Ela lê do banco e nunca fala com o broker MQTT.

- **Endereço padrão:** `http://127.0.0.1:8000` (variáveis `API_HOST` e `API_PORT`).
- **Documentação interativa (OpenAPI):** `http://127.0.0.1:8000/docs`, gerada pelo próprio código, então é sempre a referência mais atual de parâmetros e respostas.
- **Versão:** as rotas ficam em `/api/v1/...`.
- **Autenticação:** nenhuma. Por isso a API escuta só em `127.0.0.1`; veja [Privacidade](privacidade-e-lgpd.md) e o [roadmap](roadmap.md).

## Rotas

| Método | Rota | O que devolve |
|---|---|---|
| `GET` | `/health` | Estado da API (para checagem de vida). |
| `GET` | `/api/v1/devices` | Dispositivos conhecidos (que já enviaram detecções). |
| `GET` | `/api/v1/devices/{device_id}/presence` | Presença de pombos em uma janela de tempo. |
| `GET` | `/api/v1/devices/{device_id}/presence/series` | Série temporal de presença, em intervalos (`bucket`). |
| `GET` | `/api/v1/devices/{device_id}/snapshot` | Quadro JPEG atual da câmera (se configurada). |
| `GET` | `/api/v1/actuators/{actuator_id}/status` | Último estado do atuador, com a idade e se está "sem sinal". |
| `GET` | `/api/v1/controller` | Se o controlador está rodando, seu modo e a chave geral. |
| `GET` | `/api/v1/actuators/{actuator_id}/decisions` | Decisões do controlador, das mais recentes para as mais antigas. |
| `GET` | `/api/v1/actuators/{actuator_id}/events` | Eventos do atuador. |
| `POST` | `/api/v1/controller/kill-switch` | **Liga** a chave geral. Nunca desliga. |

### Janelas de tempo

As rotas de presença e de trilha aceitam `start` e `end` em ISO 8601 **com fuso** (por exemplo `2026-10-27T22:00:00Z`).

| Rota | Janela padrão | Máxima |
|---|---|---|
| Presença | 5 minutos | 31 dias |
| Série de presença | 1 hora | 31 dias |
| Decisões e eventos | 24 horas | 7 dias |

- `bucket` da série: `1m`, `5m` (padrão), `15m`, `1h` ou `1d`.
- `limit` das trilhas: de 1 a 500 registros, sempre os mais recentes.

Parâmetros fora desses limites recebem erro 4xx com o campo e o motivo explicados (veja abaixo).

### Chave geral

```http
POST /api/v1/controller/kill-switch
X-Pigeondome-Action: kill-switch-on
```

- O cabeçalho é **obrigatório**. Um cabeçalho personalizado força o navegador a fazer uma checagem prévia de CORS, o que impede que uma página qualquer dispare a ação com um formulário comum.
- A rota só **liga** a chave. Desligar exige acesso à máquina do banco (`.\scripts\kill-switch.ps1 off`). Parar é sempre seguro; rearmar exige presença.

### Quadro da câmera

`GET /api/v1/devices/{device_id}/snapshot` busca o quadro na URL configurada em `CAMERA_SNAPSHOT_URLS` e o repassa ao navegador. A API:

- espera no máximo **2 s** no total;
- aceita só **JPEG** (confere a assinatura) de até **2 MB**;
- responde com `Cache-Control: no-store` e `X-Content-Type-Options: nosniff`;
- nunca grava o quadro.

Erros: **404** quando o dispositivo não tem câmera configurada e **502** quando a câmera não entrega um quadro válido a tempo. Nos dois casos a resposta é um erro padronizado (veja abaixo), nunca o conteúdo de outro lugar.

## Erros

Os erros seguem o formato **Problem Details** ([RFC 9457](https://www.rfc-editor.org/rfc/rfc9457)), com `Content-Type: application/problem+json`:

```json
{
  "type": "urn:pigeondome:erro:...",
  "title": "resumo curto e estável",
  "status": 422,
  "detail": "explicação desta ocorrência",
  "instance": "/api/v1/...",
  "errors": [
    { "field": "start", "message": "explicação para humanos", "code": "código estável" }
  ]
}
```

- `type` e `code` são **estáveis**: dá para programar contra eles. `title` e `message` podem melhorar com o tempo.
- Erros internos (por exemplo, banco indisponível) **nunca** devolvem detalhes técnicos, caminhos ou mensagens do banco.

## CORS

Por padrão, só as origens `http://localhost:5173` e `http://127.0.0.1:5173` (o painel local) podem chamar a API pelo navegador. Para mudar, defina `API_ALLOWED_ORIGINS` (lista separada por vírgulas). Os métodos liberados são `GET` e `POST`, e o único cabeçalho extra aceito é `X-Pigeondome-Action`.
