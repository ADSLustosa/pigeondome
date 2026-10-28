# Histórico de mudanças

Segue o formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- [Dossiê do eletricista](docs/hardware/dossie-eletricista.md): rascunho do projeto elétrico da instalação de teste (arquitetura com cadeia de segurança em série, requisitos, riscos junto de placas solares, lista de materiais e comissionamento). É uma proposta para revisão profissional, não um projeto aprovado.

### Corrigido

- O painel mostrava "conexão encerrada" também para um comando recusado com o atuador desconectado. O texto agora depende do tipo do evento ("atuador desconectado" na recusa). O contrato não mudou: o par evento + motivo já era inequívoco.
- A memória do orçamento do atuador **deslocava o horário dos pulsos antigos** a cada gravação quando o relógio de parede e o monotônico discordavam (por exemplo, depois de um ajuste da hora do sistema). Agora cada pulso mantém o horário em que foi registrado.

### Segurança

- O atuador agora **guarda a sua própria trilha de eventos**, independente de rede, broker e controlador. Cada evento é gravado em disco (JSON Lines, no formato do contrato) antes de ligar a saída; se não for possível gravar, o atuador entra em falha `self_test` e não opera, mas continua podendo desligar. Rotação por tamanho (5 × 1 MiB). Novo script `show-actuator-journal.ps1` e [ADR 0008](docs/decisoes/0008-registro-de-eventos-no-proprio-atuador.md).
- O orçamento do atuador (120 s de saída por hora) agora **sobrevive a reinícios**. Antes, reiniciar o atuador zerava o limite. O gasto é gravado antes de ligar a saída; memória ilegível ou gravação com falha deixam o atuador em falha `self_test`. Nova variável `ACTUATOR_STATE_DIR` e [ADR 0007](docs/decisoes/0007-orcamento-do-atuador-sobrevive-a-reinicio.md).

## [0.1.0] - 2026-10-28

Primeira versão publicada: um protótipo **simulado**. Nenhum hardware foi construído ou avaliado.

### Adicionado

- Plataforma simulada de ponta a ponta: câmera, atuador, ingestor, controlador, API e painel, ligados por MQTT (Mosquitto, permissões por papel) e PostgreSQL.
- Contratos JSON Schema versionados para detecção, comando, estado e evento do atuador.
- Sete camadas de segurança do atuador: chave geral no banco, modo seco por padrão, política, contrato do comando, limites do atuador, estado seguro pela última vontade do broker e proteção física (planejada).
- API de leitura com erros em `application/problem+json` (RFC 9457) e painel responsivo com câmera simulada ao vivo.
- Documentação técnica em `docs/`, com registros de decisão, e READMEs de pasta.
- Identidade visual do projeto aplicada ao painel e aos READMEs, em português e inglês.
- Política de segurança, guia de participação, modelos de issue e de pull request, `CODEOWNERS`, Dependabot e análise CodeQL.
- Capturas do painel (claro, escuro, página completa e celular) nos READMEs, e script de captura por emulação de dispositivo.

### Alterado

- Licença: de MIT para **proprietária** (todos os direitos reservados). O código publicado até o commit `17696d4` continua disponível sob a MIT, nos termos descritos na [`LICENSE`](LICENSE).
- `main` protegida: mudanças só por pull request, com os checks `backend`, `simulator` e `dashboard`, e merge por squash.

[Não lançado]: https://github.com/ADSLustosa/pigeondome/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ADSLustosa/pigeondome/releases/tag/v0.1.0
