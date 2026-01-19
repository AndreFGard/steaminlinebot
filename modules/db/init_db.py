import sqlite3
import json


def init_db(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON;")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS countries (
            language VARCHAR(5) PRIMARY KEY,
            country VARCHAR(3)
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            hash TEXT NOT NULL,
            language VARCHAR(5) NOT NULL,
            FOREIGN KEY (language) REFERENCES countries(language)
        );
        """
    )

    populate_countries(db)
    return db


def populate_countries(db: sqlite3.Connection, file: str = "modules/countries.json"):
    with open(file) as f:
        countries = json.load(f)["countries"]

    db.executemany(
        """
        INSERT OR IGNORE INTO countries (language,country) VALUES (?,?)""",
        [(r["code"], r["language"]) for r in countries],
    )
    db.commit()
