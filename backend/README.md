# Backend

Ingestor, controlador e API do Pigeondome, em Python 3.12 ou superior.

| Processo | Módulo | O que faz |
|---|---|---|
| Ingestor | `python -m pigeondome` | Recebe as detecções do broker e grava no banco. Aplica as migrações. |
| Controlador | `python -m pigeondome.controller_server` | Lê as evidências, decide, comanda o atuador e registra a trilha. |
| API | `python -m pigeondome.api_server` | API REST de leitura para o painel. |

Para executar, use os scripts da raiz (`scripts\run-backend.ps1`, `run-controller.ps1` e `run-api.ps1`), que montam as credenciais de cada processo. Veja [Operação](../docs/operacao.md).

## Estrutura

```text
src/pigeondome/
├── domain/        regras puras (política, registros, frescor dos dados, quadro da câmera)
├── application/   casos de uso e portas
├── adapters/      MQTT, PostgreSQL, HTTP e adaptadores em memória
└── migrations/    SQL numerado
```

## Testes

```powershell
cd backend
pip install -e ".[dev]"
pytest -q
```

Os testes de integração com o PostgreSQL usam `PIGEONDOME_TEST_DSN` e são pulados sem ela. Qualidade: `ruff check .`, `ruff format --check .` e `mypy src` (modo estrito).

## Veja também

[Arquitetura](../docs/arquitetura.md) · [API](../docs/api.md) · [Segurança do atuador](../docs/seguranca-do-atuador.md)
