"""Database initialization — creates tables and runs migrations."""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Callable

import sqlalchemy as sql
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import event

from steaminlinebot.database.schema import country_table, game_source_table, metadata
from steaminlinebot.game.core import COMMON_GAME_SOURCE_NAMES

log = logging.getLogger(__name__)

GAME_SOURCE_SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "shop_ids_current.json"
)
COUNTRY_SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "countries.json"
)


def _ensure_schema_version(engine: sql.Engine) -> int:
    """Return the latest applied migration version, creating the tracking table if needed."""
    with engine.begin() as conn:
        conn.execute(
            sql.text(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
            )
        )
        result = conn.execute(
            sql.text("SELECT COALESCE(MAX(version), -1) FROM schema_version")
        )
        return result.scalar()  # type: ignore[no-any-return]


def _migration_000_seed_countries(engine: sql.Engine) -> None:
    with open(COUNTRY_SEED_PATH) as f:
        data = json.load(f)

    rows = [
        {"alpha2": c["code"], "language": c.get("language")} for c in data["countries"]
    ]

    with engine.begin() as conn:
        stmt = sqlite_insert(country_table).on_conflict_do_nothing(
            index_elements=["alpha2"]
        )
        conn.execute(stmt, rows)

    log.info("Seeded %d countries from %s", len(rows), COUNTRY_SEED_PATH)


def _migration_001_seed_game_sources(engine: sql.Engine) -> None:
    with open(GAME_SOURCE_SEED_PATH) as f:
        shops = json.load(f)

    rows = [{"name": s["title"], "itad_shop_id": str(s["id"])} for s in shops]

    with engine.begin() as conn:
        stmt = sqlite_insert(game_source_table).on_conflict_do_nothing(
            index_elements=["itad_shop_id"]
        )
        conn.execute(stmt, rows)

    log.info("Seeded %d game sources from %s", len(rows), GAME_SOURCE_SEED_PATH)


def _migration_002_seed_itad_source(engine: sql.Engine) -> None:
    """Insert ITAD itself as a source."""
    with engine.begin() as conn:
        exists = conn.execute(
            sql.select(game_source_table.c.id).where(
                game_source_table.c.name == COMMON_GAME_SOURCE_NAMES.ITAD.value
            )
        ).first()
        if exists is None:
            conn.execute(
                game_source_table.insert().values(
                    name=COMMON_GAME_SOURCE_NAMES.ITAD.value,
                    itad_shop_id=None,
                )
            )

    log.info("Seeded ITAD game source")


MIGRATIONS: list[tuple[int, str, Callable[[sql.Engine], None] | str]] = [
    (0, "seed country from countries.json", _migration_000_seed_countries),
    (
        1,
        "seed game_source from shop_ids_current.json",
        _migration_001_seed_game_sources,
    ),
    (2, "seed ITAD game source", _migration_002_seed_itad_source),
]


@event.listens_for(sql.Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _connection_record):
    """Enable foreign key enforcement on every new SQLite connection."""
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.execute("PRAGMA foreign_keys = ON")


def init_db(database_url: str) -> sql.Engine:
    """Create all tables, run pending migrations, and return a SQLAlchemy engine.

    Safe to call repeatedly: existing tables and migrations are skipped.
    """
    if not database_url.startswith(("sqlite:///", "postgresql://", "mysql://")):
        database_url = f"sqlite:///{database_url}"

    engine = sql.create_engine(database_url)

    metadata.create_all(engine)

    current = _ensure_schema_version(engine)
    for version, desc, action in MIGRATIONS:
        if version <= current:
            continue
        log.info("Running migration %d: %s", version, desc)
        if callable(action):
            action(engine)
        else:
            with engine.begin() as conn:
                conn.execute(sql.text(action))
        with engine.begin() as conn:
            conn.execute(
                sql.text("INSERT INTO schema_version (version) VALUES (:v)"),
                {"v": version},
            )

    return engine
