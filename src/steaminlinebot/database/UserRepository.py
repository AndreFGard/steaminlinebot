from abc import ABC, abstractmethod
import logging

from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from steaminlinebot.database.schema import country_table, user_table

log = logging.getLogger(__name__)


def _ensure_user_exists(conn: Connection, telegram_id: int) -> None:
    """Insert a bare user row if one does not already exist."""
    conn.execute(
        sqlite_insert(user_table)
        .values(telegram_id=telegram_id)
        .on_conflict_do_nothing(index_elements=["telegram_id"])
    )


class IUserRepository(ABC):
    """Data access for Telegram users and country preferences."""

    @abstractmethod
    def delete_user(self, user_id: int) -> int: ...

    # TODO: standardize a way to prefer larger countries (eg. US over Antartica, both are matches of "en")
    @abstractmethod
    def get_country_by_language(self, language: str) -> str | None:
        """Return the alpha2 country code for a language-tag match. A match is said so when the language is a prefix of such."""
        ...

    @abstractmethod
    def get_user_country(self, user_id: int) -> str | None: ...

    @abstractmethod
    def upsert_user_country(self, user_id: int, country_code: str) -> bool: ...


class UserRepository(IUserRepository):
    """SQLAlchemy-backed user/country persistence.

    Implements the same ``IUserRepository`` interface as the legacy
    sqlite3 ``UserRepository`` so that ``UserCountry`` works unchanged.

    .. note::

        The *user_id* parameter in every method is the **Telegram** user
        ID, which maps to ``user.telegram_id`` in the new schema.
    """

    def __init__(self, engine: Engine):
        self._engine = engine

    def delete_user(self, user_id: int) -> int:
        """Delete the user row identified by Telegram *user_id*.

        Returns:
            Number of rows deleted (0 or 1).
        """
        with self._engine.begin() as conn:
            result = conn.execute(
                user_table.delete().where(user_table.c.telegram_id == user_id)
            )
            return result.rowcount

    def get_country_by_language(self, language: str) -> str | None:
        language = language.lower()
        with self._engine.begin() as conn:
            row = conn.execute(
                select(country_table.c.alpha2)
                .where(country_table.c.language.startswith(language))
                .order_by(func.length(country_table.c.language).desc())
                .limit(1)
            ).first()
        return row.alpha2 if row is not None else None

    def get_user_country(self, user_id: int) -> str | None:
        """Return the ``country_alpha2`` configured for *user_id* (Telegram ID)."""
        with self._engine.begin() as conn:
            row = conn.execute(
                select(user_table.c.country_alpha2).where(
                    user_table.c.telegram_id == user_id
                )
            ).first()
        return row.country_alpha2 if row is not None else None

    # TODO: test does not allow inserting none xistant country
    def upsert_user_country(self, user_id: int, country_code: str) -> bool:
        """Insert or update the country preference for *user_id* (Telegram ID).

        Returns:
            ``True`` if the row was inserted or updated successfully.
        """
        country_code = country_code.upper()
        with self._engine.begin() as conn:
            _ensure_user_exists(conn, user_id)

            stmt = (
                user_table.update()
                .where(user_table.c.telegram_id == user_id)
                .values(country_alpha2=country_code)
            )
            result = conn.execute(stmt)
            return result.rowcount == 1
