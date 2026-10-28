# Infraestrutura

Ambiente local em contêineres Docker: PostgreSQL e Mosquitto.

| Arquivo | Para quê |
|---|---|
| `docker-compose.yml` | Sobe o Mosquitto e o PostgreSQL, publicados só em `127.0.0.1`. |
| `setup.ps1` | Prepara o ambiente: gera as senhas, escolhe uma porta livre para o banco e cria o arquivo de senhas do broker. É idempotente. |
| `mosquitto/mosquitto.conf` | Broker com senha obrigatória e ACL. |
| `mosquitto/acl` | Permissões por papel: `backend`, `camera` e `actuator`. |
| `.env.example` | Modelo das variáveis. O `.env` real é gerado e fica fora do Git. |

```powershell
.\infra\setup.ps1
docker compose --env-file infra\.env -f infra\docker-compose.yml up -d
```

Depois de editar `mosquitto/acl`, rode `scripts\apply-acl.ps1`. Detalhes em [Operação](../docs/operacao.md) e [Contratos MQTT](../docs/contratos-mqtt.md).

> [!WARNING]
> O broker escuta sem TLS e as credenciais são de desenvolvimento. Não exponha estas portas na rede.
