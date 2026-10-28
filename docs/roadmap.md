# Roadmap

O que existe, o que falta e, principalmente, **o que impede o uso com hardware real**. Esta página é a fonte de verdade do estado do projeto; o resumo do [README](../README.md#roadmap) deriva dela.

> [!IMPORTANT]
> Hoje o Pigeondome é um **protótipo simulado**. Não há evidência de que o método afaste pombos: é isso que o experimento A/B vai medir. Nenhum dispositivo que emita campo eletromagnético foi construído ou testado.

## Concluído

- [x] Contratos MQTT versionados, com JSON Schema, e ingestão idempotente
- [x] Broker com autenticação e permissões por papel (ACL) testadas
- [x] Política de decisão com modos seco, real e experimento
- [x] Atuador simulado com limites de segurança, testes unitários e teste aleatório reprodutível
- [x] Controlador com trilha de auditoria e chave geral
- [x] API de leitura com erros padronizados (RFC 9457)
- [x] Painel responsivo (a partir de 320 px), nos temas claro e escuro, com a câmera simulada ao vivo
- [x] Identidade visual e documentação técnica
- [x] Orçamento do atuador que sobrevive a reinícios (simulado em arquivo; veja o [ADR 0007](decisoes/0007-orcamento-do-atuador-sobrevive-a-reinicio.md))
- [x] Registro de eventos no próprio atuador, independente de rede (simulado em arquivo; veja o [ADR 0008](decisoes/0008-registro-de-eventos-no-proprio-atuador.md))
- [x] Registro de mudanças, primeira versão marcada (`v0.1.0`) e política de segurança
- [x] Dependabot e análise estática CodeQL no GitHub

## Antes de qualquer hardware real

Itens **bloqueantes**: sem eles, ligar o software a um dispositivo físico não é seguro.

| Item | Por que bloqueia |
|---|---|
| **Proteção física (camada 7)**: relé normalmente aberto, watchdog em hardware e limitação de corrente | Software sozinho não garante que a saída desligue se o processador travar. |
| **Orçamento do atuador em memória realmente não volátil, no hardware** | No simulador ele já sobrevive a reinício, gravado em arquivo. Falta validar no componente escolhido: memória inacessível fora do firmware e desgaste da flash. |
| **Registro de eventos do atuador à prova de adulteração, no hardware** | No simulador o atuador já registra os eventos por conta própria, mas em arquivo comum. Falta memória inacessível fora do firmware e, idealmente, encadeamento por hash. |
| **Avaliação de segurança elétrica** por profissional habilitado, conforme as normas aplicáveis | Nenhum projeto elétrico foi feito nem revisado. |
| **Conformidade legal**: legislação ambiental e sanitária aplicável ao controle de aves | Não foi avaliada. |
| **TLS no broker e autenticação na API** | Hoje tudo escuta só em `127.0.0.1`; qualquer exposição na rede precisa dos dois. |

## Próximos passos

### Evidência (o objetivo do projeto)

- [ ] **Relatório do experimento A/B**: comparar, com estatística, os blocos de tratamento e de controle. O modo `experiment` já sorteia os blocos e registra o braço de cada decisão; falta a análise.
- [ ] **Linha de base medida**: hoje a presença simulada segue um modelo por horário, que é uma suposição de modelagem. Precisa ser trocada por dados da instalação.
- [ ] **Detector real de pombos** no dispositivo de borda, com a detecção feita no próprio dispositivo (sem enviar imagem).

### Hardware

- [ ] Lista de materiais (BOM) e projeto elétrico: há um **rascunho** no [dossiê do eletricista](hardware/dossie-eletricista.md), ainda sem revisão profissional nem validação em bancada
- [ ] Avaliação normativa do projeto
- [ ] Atuador em hardware com a mesma máquina de estados do simulador: a **primeira instalação de teste usa um Raspberry Pi**, que roda o código Python já testado; o ESP32 continua sendo o alvo de um produto futuro, e exigiria reescrever o núcleo

### Robustez

- [x] Motivo `disconnected` de duas situações (conexão que cai, comando recebido com o atuador desconectado): resolvido sem mudar o contrato, pois o par evento + motivo já é inequívoco e o painel mostra o texto certo para cada um
- [ ] Política de retenção e eliminação de dados antigos
- [ ] Pausar a consulta do painel com a aba escondida em todos os blocos (hoje só a câmera faz isso)

## Fora do escopo por enquanto

- Mais de uma câmera ou mais de um atuador por instalação (o código usa identificadores, mas o painel acompanha um atuador).
- Nuvem, contas de usuário e acesso remoto.
- Qualquer uso fora do ambiente simulado.
