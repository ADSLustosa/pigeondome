# Como participar · Contributing

[Português](#português) · [English](#english)

## Português

O Pigeondome é um projeto individual com **licença proprietária**: o código está aberto para consulta, e os direitos são reservados (veja a [`LICENSE`](LICENSE)). Por isso **não aceito pull requests de código de terceiros** sem um acordo escrito com o titular.

Isso não impede que você ajude. Contribuições bem-vindas:

| O que | Como |
|---|---|
| **Erro encontrado** | Abra uma [issue de erro](https://github.com/ADSLustosa/pigeondome/issues/new/choose) com os passos para reproduzir. |
| **Dúvida ou ideia** | Abra uma [issue de ideia](https://github.com/ADSLustosa/pigeondome/issues/new/choose). |
| **Erro de texto ou de documentação** | Descreva em uma issue, com o arquivo e o trecho. Eu aplico a correção. |
| **Vulnerabilidade** | **Não** use issue pública. Siga a [política de segurança](SECURITY.md). |

### Antes de abrir uma issue

- Procure se o assunto já foi tratado em [`docs/`](docs/README.md) e no [roadmap](docs/roadmap.md).
- **Não publique dados pessoais**: imagens de câmeras com pessoas, senhas, tokens, endereços ou conteúdo do arquivo `.env`. Se um log tiver algum, apague o trecho antes de colar.
- Uma issue por assunto, com a versão ou o commit e o sistema operacional.

### Para o titular: fluxo de trabalho

A `main` é protegida: toda mudança entra por pull request, com os três checks do CI (`backend`, `simulator` e `dashboard`) verdes, e é mesclada por **squash**.

```powershell
cd backend;   ruff check .; ruff format --check .; mypy src; pytest
cd ../simulator; ruff check .; ruff format --check .; mypy src; pytest
cd ../dashboard; npm run lint; npm run build; npm test
```

Mensagens de commit seguem [Conventional Commits](https://www.conventionalcommits.org/pt-br/): `feat`, `fix`, `docs`, `test`, `build`, `ci`, `refactor`.

## English

Pigeondome is a solo project under a **proprietary license**: the source is open for viewing and all rights are reserved (see [`LICENSE`](LICENSE)). For that reason I **do not accept third-party code pull requests** without a written agreement with the owner.

You can still help:

- **Bugs:** open a [bug issue](https://github.com/ADSLustosa/pigeondome/issues/new/choose) with steps to reproduce.
- **Questions or ideas:** open an idea issue.
- **Typos and documentation errors:** describe them in an issue with the file and passage; I will apply the fix.
- **Vulnerabilities:** do **not** use a public issue; follow the [security policy](SECURITY.md).

Never post personal data in an issue: camera images showing people, passwords, tokens, addresses or `.env` contents.
