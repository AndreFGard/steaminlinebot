"""Database initialization — creates tables and runs migrations."""

import json
import logging
from pathlib import Path
from typing import Callable

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from steaminlinebot.database.schema import country_table, game_source_table, metadata

log = logging.getLogger(__name__)

GAME_SOURCE_SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "shop_ids_current.json"
)
COUNTRY_SEED_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "countries.json"
)


def _ensure_schema_version(engine: Engine) -> int:
    """Return the latest applied migration version, creating the tracking table if needed."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
            )
        )
        result = conn.execute(
            text("SELECT COALESCE(MAX(version), -1) FROM schema_version")
        )
        return result.scalar()  # type: ignore[no-any-return]


def _migration_000_seed_countries(engine: Engine) -> None:
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


def _migration_001_seed_game_sources(engine: Engine) -> None:
    with open(GAME_SOURCE_SEED_PATH) as f:
        shops = json.load(f)

    rows = [{"name": s["title"], "itad_shop_id": str(s["id"])} for s in shops]

    with engine.begin() as conn:
        stmt = sqlite_insert(game_source_table).on_conflict_do_nothing(
            index_elements=["itad_shop_id"]
        )
        conn.execute(stmt, rows)

    log.info("Seeded %d game sources from %s", len(rows), GAME_SOURCE_SEED_PATH)


MIGRATIONS: list[tuple[int, str, Callable[[Engine], None] | str]] = [
    (0, "seed country from countries.json", _migration_000_seed_countries),
    (
        1,
        "seed game_source from shop_ids_current.json",
        _migration_001_seed_game_sources,
    ),
]


def init_db(database_url: str) -> Engine:
    """Create all tables, run pending migrations, and return a SQLAlchemy engine.

    Safe to call repeatedly: existing tables and migrations are skipped.
    """
    if not database_url.startswith(("sqlite:///", "postgresql://", "mysql://")):
        database_url = f"sqlite:///{database_url}"

    engine = create_engine(database_url)

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
                conn.execute(text(action))
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": version}
            )

    return engine
