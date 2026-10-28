# Simulador

Câmera e atuador **simulados** em Python. Existem para exercitar o sistema inteiro, e provar suas proteções, sem hardware.

> [!WARNING]
> O simulador **não prova** que o método afasta pombos nem que um hardware real é seguro. A presença segue um modelo por horário, que é uma suposição de modelagem, e o atuador é software.

| Peça | Módulo | O que faz |
|---|---|---|
| Câmera | `python -m pigeondome_sim` | Publica detecções por MQTT e serve um quadro JPEG simulado em `127.0.0.1:8081`. |
| Atuador | `pigeondome_sim.actuator_runner` | Atuador simulado, com os limites de segurança, estado e eventos por MQTT. |
| Console | `actuator_console.py` | Comandos manuais e acompanhamento das mensagens. |

O núcleo do atuador (`actuator_core.py`) é uma máquina de estados pura, sem relógio nem entrada e saída: o tempo entra como parâmetro. É ele que carrega os limites de segurança. Veja [Segurança do atuador](../docs/seguranca-do-atuador.md).

O orçamento de pulsos é guardado por uma porta (`actuator_budget.py`): um arquivo JSON em `ACTUATOR_STATE_DIR` (padrão `.pigeondome-state/`), para que um reinício não zere o limite. Não apague essa pasta.

Para executar, use `scripts\run-simulator.ps1` e `scripts\run-actuator.ps1`. Veja [Operação](../docs/operacao.md).

## Testes

```powershell
cd simulator
pip install -e ".[dev]"
pytest -q
```

Inclui um teste aleatório (fuzz) reprodutível por semente, que confere as invariantes de segurança do atuador a cada passo.
