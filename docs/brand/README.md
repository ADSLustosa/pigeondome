# Pigeondome — arquivos de marca

Logo oficial: **versão vertical com descritor** ("controle inteligente de pombos").

## Qual arquivo usar

| Onde | Arquivo |
|---|---|
| README do GitHub, tela de login, apresentações, LinkedIn | `pigeondome-logo-vertical` (fundo claro) ou `-negativo` (fundo escuro) |
| Post/capa com fundo já aplicado | `pigeondome-logo-vertical-fundo-escuro` |
| Cabeçalho do painel, rodapé, barra de navegação | `pigeondome-logo-horizontal` (ou `-negativo`) |
| Ícone de app, avatar | `pigeondome-icone-app` |
| Aba do navegador | `favicon.svg` + `favicon.ico` + `png/apple-touch-icon.png` |

- **SVG** para web e impressão (vetor, escala sem perder qualidade). O texto já está convertido em contornos: não depende de fonte instalada.
- **PNG** (fundo transparente, 1200 px) para onde SVG não é aceito (LinkedIn, Office).
- **Tamanho mínimo:** a versão vertical exige pelo menos 200 px de largura (abaixo disso o descritor fica ilegível); use a horizontal ou só o símbolo.
- **Área de respiro:** mantenha em volta da logo um espaço livre igual à altura do arco interno do símbolo.
- Não distorcer, girar, aplicar sombra, contorno ou trocar as cores.

## Paleta

| Token | Hex | Uso |
|---|---|---|
| `ink` | `#23263A` | Símbolo e texto sobre fundo claro |
| `accent` | `#2F9E8F` | Arco do campo (fundo claro) |
| `muted` | `#5A5F78` | Descritor sobre fundo claro |
| `bg-dark` | `#151827` | Fundo escuro / ícone |
| `light` | `#F2F3F7` | Símbolo e texto sobre fundo escuro |
| `accent-dark` | `#4FD1BF` | Arco do campo (fundo escuro) |
| `muted-dark` | `#A9AEC4` | Descritor sobre fundo escuro |

## Tipografia

Outfit (Regular 400 em "pigeon" e no descritor; SemiBold 600 em "dome"), licença SIL Open Font License 1.1 — https://github.com/Outfitio/Outfit-Fonts

## No painel (React/Vite)

Copie `favicon.svg`, `favicon.ico` e `png/apple-touch-icon.png` para `dashboard/public/` e, no `index.html`:

```html
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
```

© Pigeondome — todos os direitos reservados.

## Neste repositório

Os arquivos oficiais ficam em [`assets/brand/`](../../assets/brand/): `svg/`, `png/` e `favicon.ico`. Os banners do README e a imagem de pré-visualização social são gerados a partir deles, com a mesma paleta, e o símbolo da cúpula inspira os arcos de fundo.

## Atenção: arquivos -negativo

Os arquivos `-negativo` são **brancos e transparentes**: sobre fundo claro ficam praticamente invisíveis (contraste de cerca de 1,1 para 1). Use-os só sobre fundo escuro. Para postagens e capas, prefira `-fundo-escuro`, que já traz o fundo aplicado.
