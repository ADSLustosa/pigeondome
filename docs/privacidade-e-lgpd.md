# Privacidade e LGPD

> [!NOTE]
> Esta é uma análise técnica do que o sistema guarda e de como ele se protege. **Não é parecer jurídico.** Antes de qualquer uso comercial ou em área com pessoas, a conformidade com a Lei Geral de Proteção de Dados (Lei nº 13.709/2018) precisa de revisão por profissional habilitado.

## Em uma frase

O sistema de hoje **não trata dados pessoais**: o banco guarda contagens, identificadores de dispositivos, decisões e motivos. A situação muda se uma câmera real passar a captar pessoas identificáveis, e o desenho já trata isso como o principal risco.

## O que existe no banco

| Tabela | O que guarda | Dado pessoal? |
|---|---|---|
| `detections` | Contagem de pombos (0 a 50), confiança, instante e identificador da câmera | Não |
| `actuation_decisions` | Veredito, motivo, contagens de evidência, modo e braço do experimento | Não |
| `actuator_events` | Aceitação, recusa, início, fim e interrupção de pulsos | Não |
| `actuator_state` | Último estado do atuador e instante da recepção | Não |
| `controller_status` | Modo, início e batimento do controlador | Não |
| `controller_flags` | Uma linha: a chave geral | Não |

Os identificadores de dispositivo seguem o padrão `^[a-z0-9-]{3,32}$` (por exemplo `cam-sim-01`). O banco os valida com `CHECK`, então não há campo de texto livre onde alguém possa escrever um nome, um endereço ou outra informação pessoal.

## O que não é guardado

- **Imagens.** O contrato de detecção declara que contém "apenas métricas, nunca imagens", e o esquema recusa qualquer campo além dos cinco definidos.
- **Imagem ao vivo.** O quadro da câmera passa pela API até o navegador e **não é gravado** em disco nem em banco. O painel o mantém só na memória e o descarta a cada quadro novo.
- **Identidade de quem usa o painel.** Não há contas nem coleta de uso. O único dado que o painel guarda no navegador é a escolha do tema, claro ou escuro.

## O risco principal: a câmera real

Uma câmera em área residencial, comercial ou industrial pode captar pessoas. Se isso acontecer, a imagem de uma pessoa identificável é **dado pessoal** (LGPD, art. 5º, I), e o tratamento passa a exigir, entre outras coisas:

- **finalidade e necessidade** definidas (art. 6º, I e III): captar só o que serve para detectar pombos;
- **base legal** adequada (art. 7º) e **transparência** com quem é captado (art. 6º, VI), por exemplo com aviso no local;
- **medidas de segurança** (art. 46) contra acesso não autorizado;
- avaliação do **relatório de impacto** (art. 38), quando cabível.

O uso estritamente particular e sem fins econômicos por uma pessoa natural fica fora da lei (art. 4º, I). O uso **comercial ou industrial**, não.

### O que o desenho já faz a favor da privacidade

| Medida | Estado |
|---|---|
| Só a contagem vai para o broker e para o banco, nunca a imagem | Implementado |
| O quadro ao vivo não é gravado | Implementado |
| A API escuta só em `127.0.0.1` e o CORS libera só a origem do painel local | Implementado |
| A URL da câmera aceita só `http` na rede local, sem usuário e senha na URL, e os erros nunca repetem a URL | Implementado |
| O tamanho e o tipo do quadro são conferidos (JPEG, até 2 MB) antes de repassar | Implementado |
| Autenticação na API e TLS no broker | **Planejado**: pré-requisito antes de qualquer exposição na rede |
| Detecção feita no próprio dispositivo de borda, sem enviar imagem | **Planejado** |

## Retenção e eliminação

**Não há política de retenção implementada.** Nenhum processo apaga dados antigos, e o banco cresce com o tempo. Como os dados atuais não são pessoais, isso não é uma violação, mas passa a ser uma obrigação se algum dado pessoal entrar. Está no [roadmap](roadmap.md).

## Segredos

As senhas do banco e do broker são geradas aleatoriamente por `infra\setup.ps1` e ficam em `infra/.env`, que o Git ignora. O repositório roda uma busca de segredos (gitleaks) antes de cada commit.

## Checklist antes de usar uma câmera real

1. Definir e documentar a finalidade e o enquadramento mínimo da câmera.
2. Avaliar a base legal e o aviso a quem circula no local.
3. Confirmar que a imagem não sai do dispositivo, ou que sai apenas com TLS e autenticação.
4. Definir prazo de retenção e rotina de eliminação.
5. Registrar quem tem acesso ao painel e ao banco.
6. Obter revisão jurídica.
