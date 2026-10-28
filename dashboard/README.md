# Painel do Pigeondome

Interface web do Pigeondome: mostra a presença de pombos, o estado do controlador e do atuador, a trilha de decisões e a câmera simulada. É somente leitura, com uma única ação de escrita: **ligar a chave geral** (parar o atuador). Desligá-la exige acesso à máquina do banco, de propósito.

## Executar

Pré-requisitos: Node.js 24 e a API rodando (`.\scripts\run-api.ps1`, na raiz do repositório).

```powershell
npm ci
npm run dev
```

O painel abre em `http://127.0.0.1:5173`. A porta é fixa porque o CORS da API só libera essa origem.

| Variável | Padrão | Para que serve |
|---|---|---|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Endereço da API. Mude se a porta 8000 estiver ocupada. |
| `VITE_ACTUATOR_ID` | `act-sim-01` | Atuador acompanhado pelo painel. |

## Comandos

| Comando | O que faz |
|---|---|
| `npm run dev` | Servidor de desenvolvimento com recarga automática. |
| `npm run build` | Verificação de tipos e build de produção. |
| `npm run lint` | ESLint. |
| `npm test` | Testes (Vitest e Testing Library). |

## Estrutura

```text
src/
  api/          cliente HTTP e tipos das respostas
  components/   blocos da tela (presença, atuação, trilha, câmera)
  hooks/        consulta periódica, tema, largura do elemento, quadro ao vivo
  lib/          funções puras: formatação, janelas de tempo, gráfico, paginação
  styles/       tokens de cor e CSS por assunto
```

## Decisões de interface

- **Dados velhos nunca parecem atuais.** Cada bloco indica a idade da informação, e a câmera só aparece como "Ao vivo" com quadro de até 5 s.
- **Consulta com cuidado.** Um pedido só começa depois que o anterior termina, e a consulta pausa com a aba escondida.
- **Responsivo até 320 px**, sem rolagem horizontal. As tabelas viram cartões em telas estreitas.
- **Tema claro e escuro**, seguindo o sistema por padrão e lembrando a escolha da pessoa.
- **Acessibilidade.** Papéis ARIA explícitos, foco visível e movimento reduzido respeitado.

Veja o [README principal](../README.md) para a visão geral e a arquitetura.
