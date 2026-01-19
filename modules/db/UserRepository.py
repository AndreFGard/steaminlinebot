import sqlite3
import logging
class UserRepository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def delete_user(self, user_id: int) -> int:
        cur = self.db.execute(
            "DELETE FROM users WHERE id = ?",
            (user_id,),
        )
        self.db.commit()
        return cur.rowcount

    def get_country_by_language(self, language):
        row = self.db.execute(
            "SELECT country from countries where language = ?",
            (language.lower(),),
        ).fetchone()
        return row[0] if row else None

    def get_user_country(self, user_id: int) -> str | None:
        row = self.db.execute(
            "SELECT u.country from users u where id=?",
            (user_id,),
        ).fetchone()
        return row[0] if row else None

    def upsert_user_country(self, user_id: int, country_code: str) -> bool:
        cur = self.db.execute(
            """
            INSERT INTO users (id, country)
            VALUES (?, ?)
            ON CONFLICT(id)
            DO UPDATE SET country = excluded.country
            """,
            (user_id, country_code.upper()),
        )

        try:
            self.db.commit()
            return cur.rowcount == 1
        except sqlite3.IntegrityError as e:
            logging.error(f"upsert user country error: {e}")
            return False

        
