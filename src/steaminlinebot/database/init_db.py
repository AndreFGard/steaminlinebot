import json
import logging
import re
import sqlite3
from decimal import Decimal
from typing import Optional

from babel.numbers import (
    get_currency_precision,
    get_territory_currencies,
    parse_decimal,
)
import pydantic

def init_db(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys = ON;")

    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_revision(
            version INTEGER
        );
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
    db.commit()

    rev0_populate_countries(db)
    rev1_migrate_prices(db)
    return db


class GameResultRowv1(pydantic.BaseModel):
    appid: int
    id: int
    country: str
    link: str
    price: str
    is_free: int
    discount: str
    date: int


class GameResultRowv2(pydantic.BaseModel):
    appid: int
    id: int
    country: Optional[str]
    link: Optional[str]
    price: Optional[str]
    price_minor: Optional[int]
    is_free: int
    discount: Optional[str]
    date: int


class CountryRow(pydantic.BaseModel):
    language_2l: str
    country: str
    currency: str


class GameResultRowCurrent(GameResultRowv2): ...


def _parse_price_minor(price: str, locale: str, currency: str) -> int:
    # strip symbols ($) but keep separators (,.)
    numeric = re.sub(r"[^\d,.\-]", "", price)

    dec = Decimal(parse_decimal(numeric, locale=locale))

    scale = get_currency_precision(currency)
    factor = Decimal(10) ** scale

    return int(dec * factor)


def rev1_migrate_prices(db: sqlite3.Connection):

    db.execute("BEGIN IMMEDIATE")

    rev = db.execute("""
        SELECT COALESCE(MAX(version),0)
        FROM schema_revision
    """).fetchone()[0]

    if rev >= 1:
        db.rollback()
        return

    # preload currency per country
    countries = db.execute("""
        SELECT DISTINCT country
        FROM gameresults
        WHERE country IS NOT NULL
    """).fetchall()

    country_currency = {c[0]: get_territory_currencies(c[0])[0] for c in countries}

    # add new columns first
    try:
        db.executescript("""
            ALTER TABLE gameresults
            ADD COLUMN price_minor INTEGER;
            ALTER TABLE countries
                RENAME COLUMN language to language_2l;
            ALTER TABLE countries ADD COLUMN currency VARCHAR(5);
        """)
    except sqlite3.OperationalError:
        # likely trying to add existing columns
        pass

    # stream rows — no giant list
    rows = db.execute("""
        SELECT id, price, g.country, language_2l
        FROM gameresults g inner join countries c
        ON g.country = c.country
        WHERE price IS NOT NULL
          AND language_2l IS NOT NULL
    """)

    for id_, price, country, language in rows:
        locale = f"{language.split('-')[0].lower()}_{country.upper()}"
        currency = country_currency[country]

        minor = _parse_price_minor(price, locale, currency)

        db.execute(
            """
            UPDATE gameresults
            SET price_minor=?
            WHERE id=?
        """,
            (minor, id_),
        )

    # add currency
    db.executemany(
        """
        UPDATE countries
        SET currency=?
        WHERE country=?
    """,
        ((country_currency[c], c) for c in country_currency),
    )

    # change language standard to 2-letter codes
    for country, langIETF in db.execute("SELECT country,language_2l FROM countries"):
        lang2l = langIETF.split("-")[0].lower()
        try:
            currency = get_territory_currencies(country)[0]
        except:
            logging.error(f"Could not get currency for country {country}")
            currency = None
        db.execute(
            """
            UPDATE countries
            SET language_2l=?,currency=?
            WHERE country=?
        """,
            (lang2l, currency, country),
        )

    db.execute("INSERT INTO schema_revision VALUES (1)")
    db.commit()


def rev0_populate_countries(
    db: sqlite3.Connection, file: str = "data/countries.json"
):
    with open(file) as f:
        countries = json.load(f)["countries"]

    db.execute("BEGIN IMMEDIATE")

    rev = db.execute("""
        SELECT COALESCE(MAX(version),0)
        FROM schema_revision
    """).fetchone()[0]

    if rev >= 0:
        db.rollback()
        return

    db.executemany(
        """
        INSERT OR IGNORE INTO countries (language_2l,country) VALUES (?,?)""",
        [(r["language_2l"], r["code"]) for r in countries],
    )
    db.commit()
