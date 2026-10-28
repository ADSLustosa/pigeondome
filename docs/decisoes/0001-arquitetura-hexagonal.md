# 0001. Arquitetura hexagonal no backend

**Estado:** aceita

## Contexto

O backend precisa decidir sobre um atuador físico. A política de decisão tem de ser testável de forma determinística, e trocar o banco ou o transporte não pode mudar uma regra de segurança.

## Decisão

O domínio (política, registros, frescor dos dados) é puro: não importa banco, rede nem relógio, e o tempo entra como parâmetro. A aplicação define portas, e MQTT, PostgreSQL e HTTP são adaptadores. Cada porta tem um adaptador em memória, e os mesmos testes de contrato rodam contra ele e contra o PostgreSQL.

## Consequências

- Cada regra de segurança tem teste unitário rápido e sem sorteio de tempo.
- Os testes de contrato impedem que a versão em memória se comporte diferente do banco real.
- Há mais arquivos e indireção do que um script único teria. O custo compensa pelo ganho em verificabilidade.
