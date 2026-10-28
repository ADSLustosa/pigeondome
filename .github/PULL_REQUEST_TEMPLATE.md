## O que muda e por quê

<!-- Uma ou duas frases. -->

## Como foi verificado

- [ ] `ruff check`, `ruff format --check` e `mypy src` (backend e simulador)
- [ ] `pytest` (backend e simulador)
- [ ] `npm run lint`, `npm run build` e `npm test` (painel)

## Segurança e privacidade

- [ ] Não afrouxa a chave geral, os limites do atuador, a política nem as permissões do broker (ou explico o motivo acima)
- [ ] Não inclui segredos, dados pessoais nem imagens de câmeras
- [ ] Atualiza `docs/` e os contratos, se o comportamento mudou
