# 0007. O orçamento do atuador sobrevive a reinícios

**Estado:** aceita

## Contexto

O atuador limita a saída a 120 s por hora ([0003](0003-limites-no-atuador-nao-no-comando.md)). Esse orçamento ficava só na memória do processo, então reiniciar o atuador, por defeito, queda de energia ou de propósito, zerava o gasto e permitia ligar a saída de novo logo em seguida. Um limite que um reinício apaga não é um limite.

Os pulsos eram guardados no relógio monotônico, que recomeça do zero a cada boot, então não podiam simplesmente ser salvos como estavam.

## Decisão

O orçamento passa a ser guardado numa memória não volátil (porta `BudgetStore`), no relógio de parede em UTC. No simulador, ela é um arquivo JSON em `ACTUATOR_STATE_DIR`, gravado de forma atômica (arquivo temporário, `fsync` e renomeação). Em hardware real seria a flash ou a EEPROM do dispositivo.

Regras, todas escolhendo o lado seguro:

- **Gravar antes de ligar.** O pulso é registrado, com o fim **previsto**, antes de a saída ligar. Se o atuador cair no meio, o pulso conta inteiro, porque não há como saber quando a saída realmente desligou.
- **Sem registro, sem pulso.** Se a gravação falhar ao aceitar um comando, ele é recusado (`fault`) e o atuador entra em falha `self_test`.
- **Memória ilegível ou duvidosa** (arquivo corrompido, de outro dispositivo, versão desconhecida): o atuador entra em falha `self_test`, guarda o arquivo ruim à parte para análise e presume que a hora seguinte já está **toda gasta**, mesmo depois de a falha sair.
- **Relógio que voltou:** um pulso gravado "no futuro" conta inteiro, como se tivesse terminado agora. O orçamento nunca diminui por causa de um relógio errado.
- O autoteste inclui confirmar que a memória grava, então um disco que não grava impede o atuador de operar já na partida.

## Consequências

- Reiniciar o atuador não zera mais o limite. Um teste aleatório com quedas de energia sorteadas confere isso ao longo de vários boots, e falha se o reinício esquecer o orçamento.
- Não houve mudança nos contratos MQTT: os motivos e códigos de falha usados já existiam.
- No simulador, quem tem acesso à pasta de estado pode apagar o arquivo e zerar o orçamento (arquivo ausente vale como primeira execução). Em hardware real, a memória precisa ser inacessível fora do firmware.
- O simulador não prova nada sobre o desgaste da flash. Há poucas gravações (no máximo 120 s de pulso por hora, duas gravações por pulso), mas isso precisa ser validado no hardware escolhido.
- O reinício de um processo simulado faz o papel do reset local: não há botão de reset no simulador.
