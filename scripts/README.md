# Scripts

Scripts PowerShell para executar e operar o ambiente local. Rode todos a partir da raiz do repositório.

| Script | Para quê |
|---|---|
| `run-backend.ps1` | Ingestor |
| `run-simulator.ps1` | Câmera simulada |
| `run-actuator.ps1` | Atuador simulado |
| `run-controller.ps1` | Controlador (`-Mode dry_run`, `live`, `experiment` ou `off`) |
| `run-api.ps1` | API (`-Port` muda a porta) |
| `kill-switch.ps1` | Chave geral: `status`, `on` ou `off` |
| `actuator-console.ps1` | Comandos manuais e `watch` das mensagens do atuador |
| `show-decisions.ps1` | A trilha do controlador, lida do banco |
| `show-actuator-journal.ps1` | A trilha do próprio atuador, lida do arquivo que ele grava |
| `smoke-api.ps1` | Teste de fumaça da API |
| `apply-acl.ps1` | Reaplica a ACL do broker |
| `capture-screenshots.ps1` | Capturas do painel para o README (chama o `capture-screenshots.mjs`, que precisa do Node) |
| `build-brand-assets.py` | Banners e imagem social, gerados dos logos oficiais |
| `mqtt-env.ps1` | Auxiliar: roda um comando com as credenciais MQTT de um papel |

Uso e variáveis em [Operação](../docs/operacao.md).
