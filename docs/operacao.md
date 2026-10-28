# Operação

Como preparar o ambiente local, executar os serviços e operar a chave geral. Os scripts são PowerShell e rodam no Windows.

> [!NOTE]
> Executar o software exige autorização do titular (veja a [licença](../LICENSE)). Este documento descreve o ambiente do projeto.

## Pré-requisitos

Windows com PowerShell, Docker Desktop, Python 3.12 ou superior, Node.js 24 e Git.

## Preparar o ambiente

Na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e "backend[dev]" -e "simulator[dev]"
.\infra\setup.ps1
docker compose --env-file infra\.env -f infra\docker-compose.yml up -d
cd dashboard
npm ci
cd ..
```

O `infra\setup.ps1` é idempotente (rodar de novo não sobrescreve nada). Ele:

- gera senhas aleatórias em `infra/.env` (que o Git ignora);
- escolhe uma porta livre para o PostgreSQL e a grava como `POSTGRES_PORT` (a padrão é 5433);
- gera o arquivo de senhas do Mosquitto, com os três papéis (`backend`, `camera`, `actuator`), e confere que o usuário do broker consegue lê-lo.

O `docker compose` sobe o PostgreSQL e o Mosquitto, ambos publicados **só em `127.0.0.1`**.

## Executar os serviços

Um terminal para cada serviço, com o `.venv` ativo, na raiz do repositório. Comece pelo ingestor, que aplica as migrações do banco.

| Serviço | Comando | Observação |
|---|---|---|
| Ingestor | `.\scripts\run-backend.ps1` | Recebe as detecções e grava no banco. |
| Câmera simulada | `.\scripts\run-simulator.ps1 -Hour 8 -IntervalSeconds 2` | `-Hour` força a hora usada pelo modelo de presença. |
| API | `.\scripts\run-api.ps1` | `-Port 8001` muda a porta. |
| Atuador simulado | `.\scripts\run-actuator.ps1` | Com os limites de segurança. Grava o orçamento em `.pigeondome-state\actuator-<id>.json` e os eventos em `actuator-<id>-events.jsonl` (`ACTUATOR_STATE_DIR` muda a pasta). |
| Registro do atuador | `.\scripts\show-actuator-journal.ps1` | Lê os eventos gravados pelo próprio atuador, mesmo com o broker parado. `-Last 50` mostra mais linhas. |
| Controlador | `.\scripts\run-controller.ps1` | Modo seco. `-Mode live` envia pulsos ao atuador simulado. |
| Painel | `cd dashboard` e `npm run dev` | Em `http://127.0.0.1:5173`. |

Sem atuador e controlador, o painel mostra presença e câmera, mas não a trilha de atuação.

> [!IMPORTANT]
> **Não apague a pasta `.pigeondome-state`.** O arquivo do orçamento é o que impede um reinício do atuador de zerar o limite da última hora; sem ele, o atuador entende que é a primeira execução. Os arquivos `*-events.jsonl` são a trilha de auditoria do atuador. Veja [Segurança do atuador](seguranca-do-atuador.md#o-orçamento-atravessa-reinícios).

### Portas

| Porta | Quem usa | Como mudar |
|---|---|---|
| 1883 | Mosquitto | `MQTT_PORT` (clientes) e o mapeamento do Compose |
| 5433 (ou a que o `setup.ps1` escolher) | PostgreSQL | `POSTGRES_PORT` em `infra/.env` |
| 8000 | API | `-Port` em `run-api.ps1` e `API_PORT` |
| 8081 | Quadro da câmera simulada | `SIM_SNAPSHOT_PORT` |
| 5173 | Painel | fixa: o CORS da API só libera esta origem |

## Modos do controlador

| Modo | O que faz |
|---|---|
| `dry_run` (padrão) | Decide e registra `would_pulse`, mas **não envia comandos**. |
| `live` | Envia pulsos ao atuador quando a política permite. |
| `experiment` | Como `live`, mas sorteia blocos de horas de controle, em que registra a decisão e não aciona. É a base do experimento A/B. |
| `off` | Não decide nada. |

```powershell
.\scripts\run-controller.ps1                  # modo seco
.\scripts\run-controller.ps1 -Mode live       # simulador recebe pulsos
```

### Variáveis do controlador

| Variável | Padrão | Significado |
|---|---|---|
| `CONTROLLER_MODE` | `dry_run` | `off`, `dry_run`, `live` ou `experiment` |
| `CONTROLLER_PULSE_S` | 5 | Duração do pulso (de 1 a 10 s) |
| `CONTROLLER_MIN_DETECTIONS` | 3 | Leituras com pombo exigidas na janela de 30 s |
| `CONTROLLER_RETRY_GAP_S` | 120 | Intervalo mínimo entre pulsos |
| `CONTROLLER_MAX_PULSES_PER_DAY` | 40 | Orçamento diário de pulsos |
| `CONTROLLER_UTC_OFFSET_HOURS` | -3 | Fuso para o "dia" e o horário de silêncio |
| `CONTROLLER_QUIET_START` / `CONTROLLER_QUIET_END` | desligado | Horas (0 a 23) do silêncio; a janela pode atravessar a meia-noite |
| `CONTROLLER_EXPERIMENT_SEED` | 0 | Semente do sorteio dos blocos |
| `CONTROLLER_TICK_S` | 1 | Ciclo do controlador (de 0,2 a 5 s) |
| `CONTROLLER_CAMERA_ID` / `CONTROLLER_ACTUATOR_ID` | `cam-sim-01` / `act-sim-01` | Dispositivos acompanhados |

Os scripts `run-*.ps1` montam o ambiente de cada processo (usuário e senha do papel MQTT, banco) a partir de `infra/.env`.

## A chave geral

```powershell
.\scripts\kill-switch.ps1 status   # mostra
.\scripts\kill-switch.ps1 on       # liga: o controlador para de comandar no próximo passo
.\scripts\kill-switch.ps1 off      # desliga: volta a poder acionar (conforme o modo)
```

- **Ligar** também é possível pelo painel (botão da chave geral) e pela [API](api.md).
- **Desligar** só por este script, na máquina do banco. É proposital: parar é sempre seguro, e rearmar exige presença.
- A chave ligada impede o **envio** de novos comandos. Para interromper um pulso em andamento, use `.\scripts\actuator-console.ps1 stop`.

## Ferramentas de apoio

| Script | Para quê |
|---|---|
| `actuator-console.ps1 pulse\|stop\|watch` | Comandos manuais ao atuador (como o papel `backend`) e acompanhamento das mensagens. |
| `show-decisions.ps1 -View decisions\|events\|summary` | A trilha do controlador, lida direto do banco. |
| `smoke-api.ps1` | Teste de fumaça: sobe a API em segundo plano, confere os códigos HTTP e encerra. |
| `apply-acl.ps1` | Reaplica dono e modo dos arquivos do broker, reinicia-o e confere os logs. Use depois de editar `infra/mosquitto/acl`, porque gravar o arquivo no Windows apaga o dono e o modo que o broker exige. |
| `capture-screenshots.ps1` | Gera as capturas do painel usadas no README. |
| `build-brand-assets.py` | Gera os banners e a imagem social a partir dos logos oficiais. |

## Testes e qualidade

```powershell
cd backend;   pytest -q; ruff check .; ruff format --check .; mypy src; cd ..
cd simulator; pytest -q; ruff check .; ruff format --check .; mypy src; cd ..
cd dashboard; npm run lint; npm run build; npm test; cd ..
```

A integração com o banco usa a variável `PIGEONDOME_TEST_DSN`; sem ela, esses testes são pulados. No GitHub, os três grupos rodam na integração contínua, e são obrigatórios para mesclar na `main`.

## Problemas conhecidos

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `connection timeout expired` ao subir a API | Banco fora do ar (Docker Desktop fechado) | Abrir o Docker Desktop e subir o Compose |
| O painel mostra erro de conexão | API fora do ar ou em outra porta | Conferir `http://127.0.0.1:8000/docs` e `VITE_API_URL` |
| A API não sobe na porta 8000 | Outro programa ocupa a porta | Veja abaixo |
| Atuador aparece "sem sinal" | Sem mensagem de estado há mais de 30 s | Conferir se o atuador e o broker estão rodando |
| `show-actuator-journal` avisa "pulso sem desfecho" | Um pulso ainda está em curso (aviso normal, some quando ele termina) ou o atuador caiu (ou foi encerrado à força) durante o pulso | Espere o pulso acabar e leia de novo. Se o aviso continuar com o atuador parado, houve queda. O orçamento já contou esse pulso inteiro. Um aviso em pulso **antigo** indica registro perdido: guarde os arquivos e investigue. |
| Controlador aparece parado | Sem batimento há mais de 15 s | Reiniciar `run-controller.ps1` |
| Atuador em falha `self_test` ao ligar | A memória do orçamento ou o registro de eventos não grava (pasta sem permissão, disco cheio), ou o arquivo do orçamento estava corrompido | Veja o log do atuador. Um arquivo ruim é guardado como `*.corrupt-*` na mesma pasta. Corrija a causa e **reinicie o atuador** (no simulador, isso faz o papel do reset local). Se o arquivo estava corrompido, a hora seguinte conta como orçamento esgotado. |

### Caso: a porta 8000 já está em uso

A 8000 é uma porta muito disputada. Uma vez, ela estava ocupada por um servidor PostgreSQL de **outro software** instalado na mesma máquina, como serviço do Windows. Encerrar o processo não adianta, porque o serviço o reinicia, e um serviço de terceiros não deve ser desativado sem saber o que ele faz.

Para descobrir quem usa a porta:

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen |
  ForEach-Object { Get-CimInstance Win32_Process -Filter "ProcessId = $($_.OwningProcess)" } |
  Select-Object ProcessId, Name, CommandLine
```

O caminho mais simples é **mudar a porta do Pigeondome**, em vez de mexer no outro programa:

```powershell
.\scripts\run-api.ps1 -Port 8001
$env:VITE_API_URL = 'http://127.0.0.1:8001'   # antes do npm run dev
```

Vale a regra geral: antes de assumir que uma porta é sua, confira quem a ocupa.
