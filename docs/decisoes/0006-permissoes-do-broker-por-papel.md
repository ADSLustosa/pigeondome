# 0006. Permissões do broker por papel

**Estado:** aceita

## Contexto

Uma câmera, um atuador e o backend têm necessidades diferentes. Se todos pudessem publicar e assinar tudo, uma câmera comprometida poderia mandar comandos.

## Decisão

O Mosquitto exige senha e usa uma ACL com três papéis: `backend`, `camera` e `actuator`. Cada um só lê e escreve o que precisa, sem curingas além do `+` do `device_id`. Os testes leem o arquivo de ACL e falham se um papel ganhar permissão a mais.

## Consequências

- Uma câmera não emite comandos, e um atuador não lê detecções.
- Mudar a ACL exige reaplicá-la (`scripts\apply-acl.ps1`), porque gravar o arquivo no Windows apaga o dono e o modo que o broker exige.
- Ainda falta TLS: as senhas trafegam em texto simples na rede local (hoje, só em `127.0.0.1`).
