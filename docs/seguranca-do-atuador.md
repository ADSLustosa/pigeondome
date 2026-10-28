# Segurança do atuador

O atuador é a única peça do sistema que, com hardware real, poderia causar dano físico. O desenho parte de uma regra: **nenhum erro de software, de rede ou de configuração pode manter a saída ligada além de limites fixos**. Cada camada se protege sozinha e não confia na anterior.

> [!IMPORTANT]
> Hoje o atuador é **simulado**. As camadas 1 a 6 existem em software e são testadas. A camada 7, a proteção física, é **planejada** e não existe. Software sozinho não substitui proteção em hardware, e nenhum hardware foi construído ou avaliado. Veja o [roadmap](roadmap.md).

## As sete camadas

| Camada | Onde | O que garante |
|---|---|---|
| **1. Chave geral** | banco de dados | Com a chave ligada, o controlador não envia nada. Sem acesso ao banco ele não decide nada, e se a linha da chave sumir, vale "ligada". A API só consegue **ligar** a chave. |
| **2. Modo seco por padrão** | controlador | Decide e registra, mas não envia comandos até que o modo real seja pedido. |
| **3. Política** | controlador | Evidência mínima, intervalo mínimo, orçamento diário e horário de silêncio. Dado velho ou atuador indisponível significa nenhuma ação. |
| **4. Contrato do comando** | JSON Schema | Validade de 1 a 30 s, identificador único e **nenhum campo de potência, tensão ou corrente**. |
| **5. Limites do atuador** | atuador | Constantes do atuador, que nenhum comando altera (tabela abaixo). |
| **6. Estado seguro** | broker MQTT | Se o atuador cai sem se despedir, o broker publica "offline" e o controlador para de comandar. |
| **7. Proteção física** | hardware (planejada) | Relé normalmente aberto e watchdog em hardware. |

### Camada 1: a chave geral só liga pela API

Parar o sistema é sempre seguro, e rearmá-lo exige presença. Por isso:

- `POST /api/v1/controller/kill-switch` só **liga** a chave e exige o cabeçalho `X-Pigeondome-Action: kill-switch-on`. Um cabeçalho personalizado força o navegador a fazer a checagem prévia de CORS, o que impede que uma página qualquer dispare a ação com um formulário.
- **Desligar** a chave só é possível com acesso à máquina do banco: `.\scripts\kill-switch.ps1 off`.

### Camada 4: o que o comando não consegue pedir

O contrato (`contracts/command.v1.schema.json`) aceita só duas ações, `pulse` e `stop`. Um `pulse` tem duração de 1 a 10 s e validade (`ttl_s`) de 1 a 30 s. **Não existe campo para potência, tensão ou corrente.** O que o atuador entrega durante um pulso é decisão do hardware, não da mensagem.

## Limites do atuador (camada 5)

São constantes do atuador (`Limits`, em `actuator_core.py`), nunca parâmetros de comando:

| Limite | Valor | Efeito |
|---|---|---|
| Pulso máximo | 10 s | Comando com duração maior é recusado (`invalid_command`). |
| Validade máxima do comando | 30 s | Comando vencido é recusado (`expired`). |
| Pausa entre pulsos | 30 s | Novo pulso na pausa é recusado (`cooldown`). |
| Orçamento | 120 s por janela de 3600 s | Pulso que estouraria o orçamento é recusado (`budget_exhausted`). |
| Watchdog | 5 s | Se o laço do atuador ficar mais de 5 s sem rodar durante um pulso, a saída é considerada desligada no prazo e o atuador entra em falha (`watchdog`). |
| Tolerância de relógio | 5 s | Comando "do futuro" além disso é recusado. |
| Relógio válido | a partir de 2026-01-01 | Relógio anterior a isso é falha no autoteste (`clock_invalid`). |
| Memória de comandos | 256 | Comandos repetidos (`command_id`) são recusados (`duplicate`). |
| Memória do orçamento | arquivo em `ACTUATOR_STATE_DIR` | O gasto da última hora sobrevive a reinício (veja abaixo). |
| Registro de eventos | arquivo em `ACTUATOR_STATE_DIR`, 1 MiB × 5 | Cada evento é gravado no próprio atuador, antes de ligar a saída (veja abaixo). |

O limite de pulso vale também no controlador: `PolicyConfig` recusa uma duração de mais de 10 s já na partida.

## O orçamento atravessa reinícios

Sem isto, reiniciar o atuador zeraria o limite de 120 s por hora. O gasto é guardado numa memória não volátil (no simulador, um arquivo; em hardware real, a flash ou a EEPROM) e recuperado ao ligar. A decisão está no [ADR 0007](decisoes/0007-orcamento-do-atuador-sobrevive-a-reinicio.md). Em resumo:

| Situação | O que o atuador faz |
|---|---|
| Aceita um pulso | **Grava antes** de ligar a saída, com o fim previsto. |
| Cai no meio de um pulso | Ao voltar, o pulso conta **inteiro**, e a pausa de 30 s também. |
| Não consegue gravar ao aceitar um comando | Recusa o comando (`fault`) e entra em falha `self_test`. |
| Arquivo corrompido, de outro dispositivo ou de versão desconhecida | Falha `self_test`, guarda o arquivo ruim à parte (`*.corrupt-*`) e presume a próxima hora como **toda gasta**. |
| Relógio de parede voltou no tempo | Pulso gravado "no futuro" conta inteiro, como se tivesse terminado agora. |
| Primeira execução (sem arquivo) | Começa com orçamento zero e confirma que consegue gravar. |

No simulador não há botão de reset: **reiniciar o processo do atuador** faz o papel do reset local, depois de corrigir a causa (pasta sem permissão, disco cheio, arquivo ruim).

## O atuador guarda a sua própria trilha

Os eventos saem por MQTT e o controlador os grava no banco, mas isso depende de rede, broker e controlador. Por isso o atuador também grava cada evento no **próprio registro**, um arquivo JSON Lines em que cada linha segue o contrato `actuator-event.v1`. A decisão está no [ADR 0008](decisoes/0008-registro-de-eventos-no-proprio-atuador.md).

| Situação | O que o atuador faz |
|---|---|
| Aceita um pulso | **Grava antes** de ligar a saída. |
| Evento com o broker fora do ar | Grava na hora; o MQTT recebe depois, ao reconectar. |
| Não consegue gravar | Falha `self_test`. Se era um comando, ele é recusado (`fault`) e a saída não liga. **Desligar nunca depende do registro.** |
| Cai no meio de um pulso | O registro termina em `pulse_started` sem desfecho, a marca da queda. |
| Cai no meio de uma gravação | Sobra uma linha cortada, que é isolada no boot seguinte e contada na leitura. |

Para ler: `.\scripts\show-actuator-journal.ps1`. Ele destaca pulso sem desfecho (normal enquanto o pulso está em curso; depois que acaba, indica queda) e linhas danificadas.

## Máquina de estados

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#E6F4F1","primaryBorderColor":"#2F9E8F","primaryTextColor":"#151827","textColor":"#151827","lineColor":"#2F9E8F","edgeLabelBackground":"#E6F4F1"}}}%%
stateDiagram-v2
  direction LR
  [*] --> safe_off
  safe_off --> idle: conectado e autoteste ok
  idle --> pulsing: comando válido
  pulsing --> cooldown: fim do pulso ou stop
  cooldown --> idle: pausa de 30 s
  idle --> maintenance: chave de manutenção
  pulsing --> maintenance: chave de manutenção
  maintenance --> idle: chave solta e autoteste ok
  idle --> fault: falha
  pulsing --> fault: falha ou watchdog
  fault --> idle: reset local e autoteste ok
```

De **qualquer** estado, perder a conexão leva a `safe_off` (por isso a seta não aparece em cada estado).

Regras que valem em qualquer estado:

- A saída (`output_on`) só pode ser verdadeira em `pulsing`. O contrato de estado proíbe qualquer outra combinação, e os testes conferem isso.
- Sem conexão (`safe_off`), a saída está desligada, e um pulso em andamento é interrompido com o motivo `disconnected`.
- **`stop` é sempre aceito**, sem validar validade, repetição nem formato, e interrompe um pulso em andamento.
- Em manutenção ou falha, todo comando é recusado, e um pulso em andamento é interrompido.
- Uma falha só sai com **reset local** (botão físico no hardware), e o primeiro código de falha é mantido. O autoteste que acompanha o reset inclui confirmar que a memória do orçamento grava.

## Ordem de validação de um `pulse`

O atuador confere, nesta ordem, e a primeira falha encerra com um evento `command_rejected` e o `reason_code` correspondente:

1. campos válidos (identificador, validade de 1 a 30 s, duração de 1 a 10 s);
2. comando não repetido;
3. emitido há pouco (não "do futuro");
4. ainda dentro da validade;
5. atuador conectado, sem falha, fora de manutenção, sem pulso e sem pausa em andamento;
6. orçamento da última hora comporta a duração pedida.

Só então a saída liga, e o atuador emite `command_accepted` e `pulse_started`.

## Como isso é verificado

| O que | Como |
|---|---|
| Regras do núcleo do atuador | Testes unitários determinísticos, com o tempo injetado (`simulator/tests/test_actuator_core.py`). |
| Invariantes sob entradas aleatórias | Teste aleatório (fuzz) reprodutível por semente: 25 sementes de 250 passos, em dois perfis de limites. A cada passo valida estado e eventos contra os contratos e, no fim, reconstrói a linha do tempo da saída (`simulator/tests/test_actuator_fuzz.py`). |
| Orçamento e reinícios | Memória do orçamento: arquivo ausente, vazio, truncado, de outro dispositivo, gravação que falha no meio. Um segundo teste aleatório sorteia quedas de energia no meio do pulso, memória ilegível e gravação com falha, e reconstrói a saída ao longo de todos os boots; ele **reprova** se um reinício esquecer o orçamento (`simulator/tests/test_actuator_budget.py` e `test_actuator_restart_fuzz.py`). |
| Registro de eventos | Arquivo: formato do contrato, rotação, linha cortada por queda, falha de gravação. Núcleo: grava **antes** de ligar a saída, recusa o pulso e entra em falha se não grava, e desliga mesmo com o registro quebrado. Teste aleatório com quedas e falhas sorteadas: o registro tem exatamente os eventos do núcleo, na ordem, e a saída nunca liga sem o início do pulso gravado (`simulator/tests/test_actuator_journal.py` e `test_actuator_restart_fuzz.py`). |
| Contratos | Os mesmos JSON Schemas validam produtores e consumidores. |
| Permissões do broker | Testes leem o arquivo de ACL e conferem que cada papel só tem o que precisa (`backend/tests/test_mosquitto_acl.py`). |
| Chave geral e falha do banco | Testes do controlador e da API conferem que a chave ligada impede o envio e que sem banco não há decisão. |

## Limitações conhecidas

Esta seção existe para que ninguém confie no que o sistema ainda não garante:

- **A memória do orçamento é um arquivo comum.** Ela simula a memória não volátil, mas quem tem acesso à pasta de estado pode apagar o arquivo e zerar o orçamento (arquivo ausente vale como primeira execução). Em hardware real, a memória precisa ser inacessível fora do firmware, e o desgaste da flash precisa ser validado no componente escolhido.
- **O registro de eventos do atuador é um arquivo comum.** Ele guarda a trilha mesmo sem rede, mas quem acessa a pasta de estado pode apagá-lo ou editá-lo, então não vale como prova. Em hardware real, precisa ficar em memória inacessível fora do firmware e, idealmente, encadeado por hash. Também não há limite de taxa: uma enxurrada de comandos recusados é gravada e pode empurrar eventos antigos para fora da rotação.
- **O motivo `disconnected` mistura duas situações:** a conexão que cai e o comando que chega com o atuador desconectado.
- **O broker não usa TLS** e a API não tem autenticação. Hoje tudo escuta só em `127.0.0.1`; qualquer exposição na rede exige as duas coisas antes.
- **A proteção física (camada 7) não existe.** Nenhum relé, watchdog em hardware ou limitador de corrente foi projetado.
- **Não houve avaliação de segurança elétrica** por profissional habilitado, nem de conformidade com a legislação ambiental e sanitária aplicável.

Todos estão no [roadmap](roadmap.md).
