# 0009. O sensor de presença é uma fonte de evidência, não uma "câmera sem imagem"

**Estado:** aceita (domínio); contrato MQTT e armazenamento ainda por fazer

## Contexto

O produto terá duas versões: a completa, com câmera e IoT, e uma básica, sem câmera. Na básica, quem pede o pulso é um sensor de presença (infravermelho passivo ou micro-ondas) na borda do telhado.

A política do controlador foi escrita para a câmera: ela exige uma contagem de pombos e uma confiança. O sensor entrega bem menos: só "há algo" ou "não há". Duas saídas eram tentadoras, e ambas são ruins:

- **Fingir que é uma detecção** (`pigeon_count = 1`, `confidence = 1`). Isso afirma que o sensor viu um pombo, e ele não sabe. Também mistura dados de fontes diferentes, o que estraga a comparação do experimento A/B.
- **Escrever uma segunda política** para o sensor. Duplicaria as regras de segurança, e duas cópias acabam divergindo.

Há ainda um risco que a câmera não tem: o sensor **não distingue pombo de pessoa**. Quem limpa as placas ou faz manutenção no telhado também dispara o pulso.

## Decisão

- A política continua **uma só**. A fonte da evidência é um parâmetro (`PolicyConfig.source`): `camera` (o padrão, comportamento idêntico ao anterior) ou `presence_sensor`.
- O sensor tem o seu próprio modelo de domínio, `PresenceReading` (instante e "presente" sim ou não). Não tem contagem nem confiança, e o nome não finge o contrário.
- A política só olha leituras da **fonte configurada**. Um sensor nunca confirma o que a câmera não viu, nem o contrário, e trocar a fonte não reaproveita dados da antiga.
- Confirmação pelo sensor: pelo menos `presence_min_positive` leituras "presente" (padrão 3) na janela de 30 s **e** a leitura mais recente ainda "presente". Se a presença acabou, não há pulso. A confiança é ignorada.
- **Sensor parado não é "ausente".** O sensor precisa enviar leituras periódicas, inclusive "ausente". Sem leituras, vale a regra de dado velho (`stale_data`) e a política não age.
- Todas as demais regras valem sem mudança e na mesma ordem: chave geral, silêncio, atuador indisponível, intervalo entre pulsos, orçamento diário, controle do experimento e modo seco como padrão. Os limites do atuador (ADR [0003](0003-limites-no-atuador-nao-no-comando.md)) são os mesmos.
- A `Evidence` de cada decisão registra a fonte (`source`). Os motivos (`reason`) não mudam: continuam estáveis para a API e o painel.

## Consequências

- O sensor **eleva o risco para pessoas**, e a política não consegue mitigar isso: ela não sabe quem disparou. As mitigações são físicas e fazem parte do projeto elétrico: chave de manutenção com chave, em série com a saída; limite de corrente na saída; condutores fora do alcance, com sinalização; sensor apontado só para a borda. Entram no [dossiê do eletricista](../hardware/dossie-eletricista.md) como requisito.
- **Falso disparo é esperado** (sol, vento, outros animais). Os valores padrão são conservadores e precisam ser calibrados no campo, em modo seco, antes de energizar.
- **Sensor travado em "presente"** continuaria pedindo pulsos, limitados pelo intervalo de 120 s, pelo orçamento diário de 40 pulsos e pelos limites do atuador. Ainda assim, uma regra de "presença contínua por tempo demais" é um próximo passo recomendado.
- Para o experimento, a fonte precisa ficar gravada junto de cada decisão. **Isso ainda não está feito:** a tabela `actuation_decisions` não tem a coluna `source` (virá numa migração, junto do contrato `presence.v1`). Até lá, o sensor só roda com decisões em memória ou no modo básico.
- Como a política é pura, a versão básica pode reutilizá-la sem banco nem broker, com os adaptadores em memória e o registro em arquivo do atuador.
