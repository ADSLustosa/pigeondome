# 0008. O atuador mantém o seu próprio registro de eventos

**Estado:** aceita

## Contexto

O atuador publica cada evento (comando aceito ou recusado, pulso iniciado, concluído ou interrompido) por MQTT, e quem os grava é o controlador, no banco. Isso deixa buracos:

- se o broker ou o controlador estiverem fora do ar, os eventos ficam guardados só na RAM do atuador, até reconectar, e **se perdem** se ele reiniciar antes;
- se o atuador cair de verdade (queda de energia), nada registra o que ele fez;
- numa disputa sobre se um pulso foi disparado, a única prova ficaria do lado de quem deu o comando.

O equipamento que aciona uma saída precisa guardar, ele mesmo, a prova do que fez.

## Decisão

O núcleo do atuador passa a gravar cada evento num registro próprio (porta `EventJournal`), independente de rede. No simulador, é um arquivo em `ACTUATOR_STATE_DIR` (`actuator-<id>-events.jsonl`), no formato JSON Lines: uma linha por evento, idêntica à mensagem do contrato `actuator-event.v1`, então o mesmo schema valida o arquivo. Em hardware real seria uma memória própria do dispositivo.

Regras, todas escolhendo o lado seguro:

- **Gravar antes de ligar.** Aceitação e início do pulso são gravados, com `fsync`, antes de a saída ligar. Os demais eventos são gravados no instante em que acontecem, conectado ou não.
- **Sem registro, sem operação.** Se a gravação falhar, o atuador entra em falha `self_test` e só volta com o reset local. Ao aceitar um comando, ele é recusado (`fault`) e a saída nunca liga. A falha **nunca impede desligar**: parar, fim de pulso, desconexão e watchdog continuam desligando a saída, mesmo com o registro quebrado.
- **O autoteste confere que o registro grava**, então um disco que não grava impede o atuador de operar já na partida.
- **Queda no meio da gravação** deixa no máximo uma linha cortada no fim do arquivo. No boot seguinte ela é isolada, o próximo evento começa em linha nova e a leitura conta a linha danificada sem perder o resto.
- **Queda no meio de um pulso** aparece como um `pulse_started` sem `pulse_finished` nem `pulse_aborted`. É a marca da queda, e o leitor a destaca. O orçamento já conta esse pulso inteiro (ADR [0007](0007-orcamento-do-atuador-sobrevive-a-reinicio.md)).
- **Rotação por tamanho:** 1 MiB por arquivo, mantendo 5 (cerca de 5 MiB). Os eventos têm só identificador do comando e horário, **sem dados pessoais**, então a retenção é questão de espaço, não de privacidade.

O contrato MQTT não mudou.

## Consequências

- Com o controlador parado, o atuador continua registrando. Um teste aleatório com quedas de energia confere que o registro contém exatamente os eventos do núcleo, na ordem, ao longo de vários boots, e que a saída nunca está ligada sem o início do seu pulso gravado, mesmo com a gravação falhando.
- O registro não está protegido contra alteração: quem acessa a pasta pode apagá-lo ou editá-lo. Para valer como prova, em hardware real ele precisa ficar em memória inacessível fora do firmware, e idealmente encadeado por hash. Isso não está feito.
- Uma enxurrada de comandos recusados também é gravada, a 1 `fsync` por evento, e pode empurrar eventos antigos para fora da rotação. O acesso ao tópico de comandos é restrito por ACL do broker, mas não há limite de taxa.
- No Windows, a rotação falha se outro programa estiver com o arquivo aberto sem permitir renomear; a falha vira falha `self_test`, o lado seguro. Leia o registro com o script, que abre o arquivo só para leitura.
- A ordem entre registro e orçamento ao aceitar um pulso é: primeiro o orçamento, depois o registro. Se o registro falhar, o orçamento fica com um pulso que não aconteceu (conta como gasto, o lado conservador), mas o registro nunca afirma um pulso que não houve.
