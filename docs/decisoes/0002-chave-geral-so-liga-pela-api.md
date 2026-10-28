# 0002. A chave geral só liga pela API

**Estado:** aceita

## Contexto

O painel precisa poder parar o sistema depressa. Mas uma rota que também **desligasse** a chave permitiria que um erro, uma página maliciosa ou um acesso indevido rearmasse o atuador.

## Decisão

A chave geral fica no banco. A API tem uma única rota de escrita, que só **liga** a chave e exige o cabeçalho `X-Pigeondome-Action: kill-switch-on`, o que força a checagem prévia de CORS no navegador. **Desligar** só é possível por `scripts\kill-switch.ps1 off`, na máquina do banco. Sem acesso ao banco, o controlador não decide nada, e se a linha da chave sumir, vale "ligada".

## Consequências

- Parar é sempre seguro e rápido; rearmar exige presença física.
- O painel não consegue reativar o sistema, mesmo comprometido.
- Quem opera precisa de acesso à máquina do banco para voltar a acionar, o que é um custo aceito.
