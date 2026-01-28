import sqlite3
import json


def init_db(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON;")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS countries (
            language VARCHAR(5),
            country VARCHAR(5) PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            country VARCHAR(5) NOT NULL,
            FOREIGN KEY (country) REFERENCES countries(country)
        );


        CREATE TABLE IF NOT EXISTS gameresults (
            appid INTEGER,
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT,
            link TEXT,
            price TEXT,
            is_free INTEGER,
            discount TEXT,
            date INTEGER
        );

        CREATE TABLE IF NOT EXISTS protondbresults (
            appid INTEGER,
            id INTEGER,
            bestReportedTier TEXT,
            confidence TEXT,
            score REAL,
            tier TEXT,
            total INTEGER,
            trendingTier TEXT,
            PRIMARY KEY (id),
            FOREIGN KEY (id)
            REFERENCES gameresults (id)
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
        [( r["language"],r["code"]) for r in countries],
    )
    db.commit()
