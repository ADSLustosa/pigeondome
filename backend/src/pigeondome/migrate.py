"""Migrações versionadas: arquivos SQL numerados, aplicados uma única vez e em ordem."""

from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
LOCK_KEY = 727274  # identifica "migrações do pigeondome" no advisory lock


def migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(directory.glob("*.sql"))


def apply_migrations(conninfo: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Aplica as migrações pendentes. Devolve os nomes aplicados agora."""
    applied_now: list[str] = []
    # autocommit: cada migração roda na sua própria transação explícita
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
            done = {row[0] for row in rows}
            for path in migration_files(directory):
                if path.name in done:
                    continue
                # os arquivos SQL fazem parte do código-fonte, nunca de entrada externa
                sql = path.read_bytes()
                with conn.transaction():
                    conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
                applied_now.append(path.name)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
    return applied_now
