# 0004. A hora de recepção define o que é dado velho

**Estado:** aceita

## Contexto

O painel não pode mostrar um atuador parado como se estivesse bem. O `reported_at` vem do relógio do dispositivo, que pode estar errado ou congelado.

## Decisão

A idade de um estado conta a partir da **hora de recepção**, pelo relógio do controlador. Um atuador `online` sem mensagem há mais de 30 s é "sem sinal". Um atuador `offline` é um fato, informado pelo aviso de última vontade do broker, e não é tratado como velho. O controlador está vivo se o batimento tem até 15 s.

## Consequências

- Um relógio errado no dispositivo não esconde uma queda.
- Painel e controlador usam o mesmo limite de 30 s, então concordam sobre o que é velho.
- Depende de o relógio do controlador estar correto.
