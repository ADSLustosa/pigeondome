# Política de segurança · Security policy

[Português](#português) · [English](#english)

## Português

### Como relatar uma vulnerabilidade

**Não abra uma issue pública.** Use o relato privado do GitHub:

1. Abra a aba [**Security**](https://github.com/ADSLustosa/pigeondome/security) do repositório.
2. Clique em **Report a vulnerability** e descreva o problema.

Se o botão não estiver disponível, peça um canal privado pelo [LinkedIn](https://www.linkedin.com/in/adslustosa), **sem** descrever a falha na mensagem.

Inclua, se puder: o componente afetado (broker, ingestor, controlador, atuador, API ou painel), os passos para reproduzir, o impacto que você percebe e a versão ou o commit.

### O que esperar

| Etapa | Meta |
|---|---|
| Confirmação de recebimento | até 5 dias úteis |
| Primeira avaliação | até 15 dias úteis |
| Correção ou plano | informado após a avaliação, conforme a gravidade |

Este é um projeto individual, então os prazos são metas de boa-fé, não garantias contratuais. Peço que a falha não seja divulgada antes de existir uma correção ou um acordo sobre o prazo.

### O que está no escopo

- Burlar a **chave geral**, os **limites do atuador** ou a **política** de decisão (veja [Segurança do atuador](docs/seguranca-do-atuador.md)).
- Contornar as **permissões do broker** por papel ou o contrato dos comandos.
- Falhas na API (por exemplo, injeção, vazamento de detalhes internos ou CORS indevido) e no painel.
- Segredos ou dados pessoais expostos no repositório.

### Limitações já conhecidas (fora do escopo)

Estão documentadas e planejadas no [roadmap](docs/roadmap.md), então relatá-las não é necessário: ausência de TLS no broker e de autenticação na API (hoje tudo escuta só em `127.0.0.1`), orçamento do atuador gravado em arquivo comum (simula a memória não volátil), registro de eventos do atuador em arquivo comum (sem proteção contra alteração) e proteção física inexistente.

### Versões suportadas

O projeto está em desenvolvimento inicial. Só a `main` recebe correções.

> [!IMPORTANT]
> O atuador é **simulado**. Nenhum hardware foi construído ou avaliado, e o software não deve ser ligado a uma saída física sem proteção em hardware e avaliação por profissional habilitado.

## English

### Reporting a vulnerability

**Please do not open a public issue.** Use GitHub's private reporting:

1. Open the repository's [**Security**](https://github.com/ADSLustosa/pigeondome/security) tab.
2. Click **Report a vulnerability** and describe the problem.

If the button is unavailable, ask for a private channel on [LinkedIn](https://www.linkedin.com/in/adslustosa) **without** describing the flaw in the message.

Please include, if you can: the affected component (broker, ingestor, controller, actuator, API or dashboard), steps to reproduce, the impact you see, and the version or commit.

### What to expect

This is a solo project, so these are good-faith targets, not contractual guarantees: acknowledgement within 5 business days, a first assessment within 15 business days, and a fix or plan after that, depending on severity. Please do not disclose the flaw before a fix exists or a timeline has been agreed.

### Scope

In scope: bypassing the **kill switch**, the **actuator limits** or the decision **policy**; getting around per-role **broker permissions** or the command contract; API and dashboard flaws; secrets or personal data exposed in the repository.

Out of scope, because they are already documented in the [roadmap](docs/roadmap.md): no TLS on the broker and no API authentication (everything listens on `127.0.0.1` only), the actuator budget stored in a plain file (it simulates non-volatile memory), events recorded only by the controller, and the absence of physical protection.

### Supported versions

Early development. Only `main` receives fixes. The actuator is **simulated**: no hardware has been built or assessed.
