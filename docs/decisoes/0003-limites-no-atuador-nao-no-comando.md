# 0003. Os limites de segurança pertencem ao atuador

**Estado:** aceita

## Contexto

Se o limite de duração, a pausa ou o orçamento viessem no comando, um bug ou uma mensagem forjada no controlador poderia ultrapassá-los.

## Decisão

Pulso máximo, pausa, orçamento por hora e watchdog são constantes do atuador (`Limits`). O contrato do comando não tem campo de potência, tensão ou corrente, e `stop` é sempre aceito. O atuador recusa tudo que ultrapassa os limites, e registra o motivo.

## Consequências

- O controlador pode errar sem que a saída fique ligada além do limite.
- A política do controlador repete o limite de pulso para recusar configuração inválida cedo, mas **não é ela que protege**.
- Mudar um limite exige alterar o atuador, não a configuração do controlador.
