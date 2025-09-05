"""
Setup PostgreSQL: create role + database (idempotent), enforce UTF-8 client and ASCII messages.
Run from project root (parent of package 'app'):  python -m app.setup_database

Env overrides (optional):
  PGHOST, PGPORT, PGSUPERUSER, PGSUPERPASS, PGUSER, PGPASSWORD, PGDATABASE
"""

from __future__ import annotations

import logging
import os
from typing import Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger("setup_db")

# -----------------------------------------------------------------------------
# Config via env (avec défauts sûrs)
# -----------------------------------------------------------------------------
PGUSER: Optional[str] = "liauser"
PGPASSWORD: Optional[str] = "liapass123"
PGHOST: Optional[str] = "localhost"
PGPORT: Optional[int] = 5432
PGDATABASE: Optional[str] = "lia_coaching"

# Options libpq : forcer encodage client et messages ASCII (évite UnicodeDecodeError)
LIBPQ_OPTIONS = "-c client_encoding=UTF8 -c lc_messages=C"


# -----------------------------------------------------------------------------
# Connexions (avec encodage forcé)
# -----------------------------------------------------------------------------
def connect_super(db: str = "postgres") -> psycopg2.extensions.connection:
    params = dict(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        dbname=db,
        options=LIBPQ_OPTIONS,
    )
    conn = psycopg2.connect(**params)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    conn.set_client_encoding("UTF8")
    return conn


def connect_app() -> psycopg2.extensions.connection:
    params = dict(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        dbname=PGDATABASE,
        options=LIBPQ_OPTIONS,
    )
    conn = psycopg2.connect(**params)
    conn.set_client_encoding("UTF8")
    return conn


# -----------------------------------------------------------------------------
# Utilitaires SQL idempotents
# -----------------------------------------------------------------------------
def show_encodings(cur, label: str) -> None:
    cur.execute("SHOW SERVER_ENCODING;")
    server_enc = cur.fetchone()[0]
    cur.execute("SHOW CLIENT_ENCODING;")
    client_enc = cur.fetchone()[0]
    log.info("[%s] server_encoding=%s, client_encoding=%s", label, server_enc, client_enc)


def ensure_role(cur, username: str, password: str) -> None:
    """Crée le rôle s'il n'existe pas, synchronise le mot de passe sinon."""
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (username,))
    if cur.fetchone():
        log.info("Role '%s' already exists → syncing password", username)
        cur.execute(
            sql.SQL("ALTER ROLE {} WITH PASSWORD %s").format(sql.Identifier(username)),
            (password,),
        )
    else:
        cur.execute(
            sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(username)),
            (password,),
        )
        log.info("Role '%s' created", username)


def ensure_database(cur, dbname: str, owner: str) -> None:
    """Crée la DB en UTF-8 si absente (via template0)."""
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone():
        log.info("Database '%s' already exists", dbname)
    else:
        cur.execute(
            sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0")
               .format(sql.Identifier(dbname), sql.Identifier(owner))
        )
        log.info("Database '%s' created (UTF8)", dbname)


def grant_privileges_on_db(cur, dbname: str, user: str) -> None:
    cur.execute(
        sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}")
           .format(sql.Identifier(dbname), sql.Identifier(user))
    )
    log.info("Granted DB privileges on '%s' to '%s'", dbname, user)


def tune_schema_privileges(dbname: str, user: str) -> None:
    """
    Dans la DB cible, accorde privilèges sur public et règle les default privileges
    pour les futurs objets du rôle (tables + séquences).
    """
    with connect_super(dbname) as conn:
        with conn.cursor() as cur:
            show_encodings(cur, f"super/{dbname}")

            # Privilèges sur le schéma public
            cur.execute(
                sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(user))
            )

            # Privilèges sur objets existants
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {}")
                   .format(sql.Identifier(user))
            )
            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {}")
                   .format(sql.Identifier(user))
            )

            # Default privileges pour futurs objets créés par ce rôle
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT ALL ON TABLES TO {}"
                ).format(sql.Identifier(user), sql.Identifier(user))
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public "
                    "GRANT ALL ON SEQUENCES TO {}"
                ).format(sql.Identifier(user), sql.Identifier(user))
            )
            log.info("Schema privileges set for '%s'", user)


# -----------------------------------------------------------------------------
# Pipeline
# -----------------------------------------------------------------------------
def main() -> int:
    log.info("PostgreSQL setup start")
    log.info("Target DB: %s | User: %s | Host: %s:%s", PGDATABASE, PGUSER, PGHOST, PGPORT)

    try:
        # Connexion superuser à la DB postgres
        with connect_super("postgres") as conn:
            with conn.cursor() as cur:
                show_encodings(cur, "super/postgres")
                ensure_role(cur, PGUSER, PGPASSWORD)
                ensure_database(cur, PGDATABASE, PGUSER)
                grant_privileges_on_db(cur, PGDATABASE, PGUSER)

        # Réglages de privilèges au sein de la DB cible
        tune_schema_privileges(PGDATABASE, PGUSER)

        # Test final avec l'utilisateur applicatif
        with connect_app() as conn:
            with conn.cursor() as cur:
                show_encodings(cur, f"app/{PGDATABASE}")
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
        log.info("Connection test OK with '%s' → %s", PGUSER, version)
        log.info("PostgreSQL setup done ✅")
        return 0

    except psycopg2.OperationalError:
        # Ici tu verras enfin l'erreur réelle (mdp incorrect, service down, port fermé…)
        log.exception("OperationalError: check server/credentials/service/port")
        return 2
    except Exception:
        log.exception("Unexpected error during setup")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
