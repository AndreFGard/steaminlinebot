import pytest
from sqlalchemy import create_engine, select
import sqlalchemy
from typing import Optional

from steaminlinebot.database.schema import (
    country_table,
    game_external_id_table,
    game_source_table,
    game_table,
    historical_low_table,
    metadata,
)
from steaminlinebot.database.game_repository import (
    GameRepository,
    SourceNotFoundError,
)
from steaminlinebot.game.core import (
    ProductType,
    COMMON_GAME_SOURCE_NAMES,
    GameDeal,
    HistoricalPriceData,
    LowestPriceInPeriod,
)


def _setup_engine() -> "sqlalchemy.Engine":
    """Create an in-memory SQLite engine pre-seeded with ``country`` and the Steam source."""
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(country_table.insert().values(alpha2="US"))
        conn.execute(country_table.insert().values(alpha2="BR"))
        conn.execute(game_source_table.insert().values(name="Steam", itad_shop_id="61"))
    return engine


def _seed_source(
    engine: "sqlalchemy.Engine", name: str, itad_shop_id: Optional[str] = None
) -> None:
    """Insert an additional game source (e.g. ITAD) into the engine."""
    with engine.begin() as conn:
        conn.execute(
            game_source_table.insert().values(name=name, itad_shop_id=itad_shop_id)
        )


def _make_deal(
    value_minor: int = 999,
    currency_3l: str = "USD",
    full_value_minor: int = 1999,
    discount: int = 50,
    country_l2: str = "US",
    price_expires_at=None,
    observed_date=None,
    historical_deal=None,
    url: str = "https://store.steampowered.com/app/730/",
) -> GameDeal:
    return GameDeal(
        value_minor=value_minor,
        currency_3l=currency_3l,
        full_value_minor=full_value_minor,
        discount=discount,
        country_l2=country_l2,
        price_expires_at=price_expires_at,
        observed_date=observed_date,
        historical_deal=historical_deal,
        source_shop="Steam",
        url=url,
    )


def _make_price_overview(
    scope: LowestPriceInPeriod = LowestPriceInPeriod.ALL,
    lowest_value_minor: int = 500,
    country_l2: str = "US",
    currency_3l: str = "USD",
) -> HistoricalPriceData:
    return HistoricalPriceData(
        scope=scope,
        lowest_value_minor=lowest_value_minor,
        country_l2=country_l2,
        currency_3l=currency_3l,
    )


class TestInsertGame:
    """Happy-path and edge cases for inserting a game via the repository."""

    def test_returns_game_id_and_links_source(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Hollow Knight",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "367520",
        )

        assert isinstance(game_id, int) and game_id > 0
        assert (
            repo.get_game_id_on_source(game_id, COMMON_GAME_SOURCE_NAMES.STEAM)
            == "367520"
        )

    def test_reuses_existing_game(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        first = repo.get_or_insert_game(
            "Hollow Knight",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "367520",
        )
        second = repo.get_or_insert_game(
            "Hollow Knight",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "367520",
        )

        assert first == second


class TestSourceNotFound:
    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        with pytest.raises(SourceNotFoundError, match="ITAD"):
            repo.get_or_insert_game(
                "Counter-Strike",
                ProductType.GAME,
                COMMON_GAME_SOURCE_NAMES.ITAD.value,
                "730",
            )


class TestHistoricalLow:
    """``price_overview`` is persisted into the historical_low table."""

    def test_inserts_historical_low(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        pov = _make_price_overview(
            lowest_value_minor=500,
            country_l2="US",
            currency_3l="USD",
            scope=LowestPriceInPeriod.ALL,
        )
        repo.upsert_historical_price(game_id, pov)

        with engine.begin() as conn:
            rows = conn.execute(historical_low_table.select()).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.game_id == game_id
        assert row.country_alpha2 == "US"
        assert row.currency == "USD"
        assert row.lowest_value_minor == 500
        assert row.scope.value == "all"

    def test_updates_historical_low(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        repo.upsert_historical_price(
            game_id,
            _make_price_overview(
                lowest_value_minor=500,
                country_l2="US",
                currency_3l="USD",
                scope=LowestPriceInPeriod.ALL,
            ),
        )
        repo.upsert_historical_price(
            game_id,
            _make_price_overview(
                lowest_value_minor=100,
                country_l2="US",
                currency_3l="USD",
                scope=LowestPriceInPeriod.ALL,
            ),
        )

        with engine.begin() as conn:
            rows = conn.execute(historical_low_table.select()).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.game_id == game_id
        assert row.country_alpha2 == "US"
        assert row.currency == "USD"
        assert row.lowest_value_minor == 100
        assert row.scope.value == "all"


class TestAddGameSource:
    def test_links_game_to_source_external_id(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        repo.add_game_source(
            game_id,
            game_source=COMMON_GAME_SOURCE_NAMES.ITAD,
            external_id="itad-123",
        )

        with engine.begin() as conn:
            itad_id = conn.execute(
                select(game_source_table.c.id).where(game_source_table.c.name == "ITAD")
            ).scalar_one()
            row = conn.execute(
                select(game_external_id_table).where(
                    game_external_id_table.c.game_id == game_id,
                    game_external_id_table.c.source_id == itad_id,
                )
            ).first()

        assert row is not None
        assert row.external_id == "itad-123"


class TestGetGameSource:
    def test_gets_source_when_exists(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        external_id = repo.get_game_id_on_source(
            game_id, COMMON_GAME_SOURCE_NAMES.STEAM
        )

        assert external_id == "730"

    def test_gets_source_when_multiple_sources_exist(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        repo.add_game_source(
            game_id,
            game_source=COMMON_GAME_SOURCE_NAMES.ITAD,
            external_id="itad-123",
        )
        external_id = repo.get_game_id_on_source(
            game_id, COMMON_GAME_SOURCE_NAMES.STEAM
        )

        assert external_id == "730"

    def test_filters_by_game_id_not_just_source(self):
        """Regression: get_game_id_on_source must honor game_id, not only source_id."""
        engine = _setup_engine()
        repo = GameRepository(engine)

        steam_a = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "730",
        )
        steam_b = repo.get_or_insert_game(
            "Counter-Strike",
            ProductType.GAME,
            COMMON_GAME_SOURCE_NAMES.STEAM.value,
            "999",
        )

        ext_a = repo.get_game_id_on_source(steam_a, COMMON_GAME_SOURCE_NAMES.STEAM)
        ext_b = repo.get_game_id_on_source(steam_b, COMMON_GAME_SOURCE_NAMES.STEAM)

        assert ext_a == "730"
        assert ext_b == "999"
        assert ext_a != ext_b
