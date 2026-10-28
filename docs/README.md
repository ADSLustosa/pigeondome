# Documentação

Documentação técnica do Pigeondome. Ela descreve **o que o código faz hoje**; o que ainda não existe está marcado como planejado e reunido no [roadmap](roadmap.md).

> [!NOTE]
> Estes documentos são técnicos, não pareceres jurídicos nem laudos de segurança elétrica. Onde a lei ou uma norma entra, o texto diz o que foi e o que não foi avaliado.

## Por onde começar

| Se você quer... | Leia |
|---|---|
| Entender como as peças se encaixam | [Arquitetura](arquitetura.md) |
| Saber por que o atuador não pode causar dano por software | [Segurança do atuador](seguranca-do-atuador.md) |
| Ver quais dados existem e o que a LGPD muda | [Privacidade e LGPD](privacidade-e-lgpd.md) |
| Integrar um dispositivo ao broker | [Contratos MQTT](contratos-mqtt.md) |
| Consultar a API | [API](api.md) |
| Subir o ambiente e operar a chave geral | [Operação](operacao.md) |
| Saber o que falta antes de usar com hardware real | [Roadmap](roadmap.md) |
| Entender por que uma escolha foi feita | [Decisões de arquitetura](decisoes/README.md) |
| Usar a identidade visual | [Guia de marca](brand/README.md) |

## Ordem de leitura sugerida

1. [Arquitetura](arquitetura.md), para o mapa geral.
2. [Segurança do atuador](seguranca-do-atuador.md), a parte que justifica o desenho do resto.
3. [Contratos MQTT](contratos-mqtt.md) e [API](api.md), as duas fronteiras do sistema.
4. [Operação](operacao.md), para executar.
5. [Roadmap](roadmap.md), para saber os limites do que existe.

Cada pasta de código tem um `README.md` curto que aponta para estes documentos: [`backend/`](../backend/README.md), [`simulator/`](../simulator/README.md), [`contracts/`](../contracts/README.md), [`infra/`](../infra/README.md), [`scripts/`](../scripts/README.md) e [`dashboard/`](../dashboard/README.md).
