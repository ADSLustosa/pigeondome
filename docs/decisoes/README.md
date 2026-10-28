# Decisões de arquitetura

Registros curtos (ADR) das escolhas que mais pesam no projeto: o contexto, o que foi decidido e o que isso custa. Servem para que ninguém desfaça uma decisão de segurança sem saber por que ela existe.

| Nº | Decisão |
|---|---|
| 0001 | [Arquitetura hexagonal no backend](0001-arquitetura-hexagonal.md) |
| 0002 | [A chave geral só liga pela API](0002-chave-geral-so-liga-pela-api.md) |
| 0003 | [Os limites de segurança pertencem ao atuador](0003-limites-no-atuador-nao-no-comando.md) |
| 0004 | [A hora de recepção define o que é dado velho](0004-hora-de-recepcao-define-dado-velho.md) |
| 0005 | [Modo seco por padrão e regras em ordem fixa](0005-modo-seco-por-padrao.md) |
| 0006 | [Permissões do broker por papel](0006-permissoes-do-broker-por-papel.md) |
| 0007 | [O orçamento do atuador sobrevive a reinícios](0007-orcamento-do-atuador-sobrevive-a-reinicio.md) |
| 0008 | [O atuador mantém o seu próprio registro de eventos](0008-registro-de-eventos-no-proprio-atuador.md) |

## Como acrescentar uma decisão

1. Crie `NNNN-titulo-curto.md` com o próximo número.
2. Use as seções **Contexto**, **Decisão** e **Consequências**, em poucas linhas.
3. Se uma decisão for substituída, não apague a antiga: troque o estado dela para "substituída por NNNN" e crie a nova.
