import sqlite3

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

    def get_country(self, language):
        row = self.db.execute(
            "SELECT country from countries where language = ?",
            (language,),
        ).fetchone()
        return row[0] if row else None

    def get_user_country(self, user_id: int) -> str | None:
        row = self.db.execute(
            "SELECT country FROM users u inner join countries c on c.language = u.language WHERE id = ?",
            (user_id,),
        ).fetchone()
        return row[0] if row else None

    def upsert_language(self, user_id: int, language: str) -> None:
        self.db.execute(
            """
            INSERT INTO users (id, language)
            VALUES (?, ?)
            ON CONFLICT(id)
            DO UPDATE SET language = excluded.language
            """,
            (user_id, language),
        )
        self.db.commit()
    
