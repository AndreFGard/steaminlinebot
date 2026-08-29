import pytest
from sqlalchemy import create_engine, select
import sqlalchemy
from typing import Optional

from steaminlinebot.database.schema import (
    country_table,
    game_external_id_table,
    game_source_table,
    historical_low_table,
    metadata,
)
from steaminlinebot.database.game_repository import (
    GameRepository,
    SourceNotFoundError,
)
from steaminlinebot.game.core import (
    ProductType,
    GameSource,
    Game,
    SourcedGame,
    GameDeal,
    HistoricalPriceData,
    LowestPriceInPeriod,
)
from steaminlinebot.game.protondb_report import ProtonDBReport, ProtonDBTier
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport


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


def _make_report(
    best_reported_tier: ProtonDBTier = ProtonDBTier.GOLD,
    confidence: str = "Strong",
    score: float = 0.9,
    tier: ProtonDBTier = ProtonDBTier.GOLD,
    total: int = 1500,
    trending_tier: ProtonDBTier = ProtonDBTier.PLATINUM,
) -> ScrapedProtonDBReport:
    return ScrapedProtonDBReport(
        best_reported_tier=best_reported_tier,
        confidence=confidence,
        score=score,
        tier=tier,
        total=total,
        trending_tier=trending_tier,
    )


def _insert_full_game(
    repo: GameRepository,
    *,
    title: str = "Counter-Strike",
    product_type: ProductType = ProductType.GAME,
    external_id: str = "730",
    url: str = "https://store.steampowered.com/app/730/",
    deals: Optional[list[GameDeal]] = None,
    game_source: GameSource = GameSource.STEAM,
    price_overview: Optional[HistoricalPriceData] = None,
    proton_db_report: Optional[ScrapedProtonDBReport] = None,
) -> SourcedGame:
    """Insert a game through the public repository API with sensible defaults."""
    if deals is None:
        deals = [_make_deal()]
    return repo.insert_full_game(
        title=title,
        product_type=product_type,
        external_id=external_id,
        url=url,
        deals=deals,
        game_source=game_source,
        price_overview=price_overview,
        proton_db_report=proton_db_report,
    )


def _strip_ids(obj):
    """Recursively remove auto-generated ID keys (``id``, ``game_id``, etc.)."""
    if hasattr(obj, "model_dump"):
        d = obj.model_dump()
    elif isinstance(obj, dict):
        d = obj
    else:
        return obj

    _ID_KEYS = {"id", "game_id"}

    result = {}
    for k, v in d.items():
        if k in _ID_KEYS:
            continue
        if isinstance(v, dict):
            result[k] = _strip_ids(v)
        elif isinstance(v, list):
            result[k] = [_strip_ids(item) for item in v]
        else:
            result[k] = v
    return result


def assert_model_equal(actual, expected, msg: str = ""):
    """Assert two pydantic models are equal **ignoring auto-generated ID fields**."""
    assert _strip_ids(actual) == _strip_ids(expected), (
        f"{msg}\n"
        f"actual (stripped):  {_strip_ids(actual)}\n"
        f"expected (stripped): {_strip_ids(expected)}"
    )


class TestInsertFullGame:
    """Happy-path: game with a deal + ProtonDB report."""

    def test_returns_correct_fields(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = _insert_full_game(repo, proton_db_report=_make_report())

        expected = SourcedGame(
            game=Game(id=0, title="Counter-Strike", product_type=ProductType.GAME),
            external_id="730",
            game_source=GameSource.STEAM,
            deals=[
                GameDeal(
                    value_minor=999,
                    currency_3l="USD",
                    full_value_minor=1999,
                    discount=50,
                    country_l2="US",
                    price_expires_at=None,
                    observed_date=None,
                    historical_deal=None,
                )
            ],
            url="https://store.steampowered.com/app/730/",
            price_overview=None,
            proton_db_info=ProtonDBReport(
                game_id=0,  # stripped
                best_reported_tier=ProtonDBTier.GOLD,
                confidence="Strong",
                score=0.9,
                tier=ProtonDBTier.GOLD,
                total=1500,
                trending_tier=ProtonDBTier.PLATINUM,
            ),
        )

        assert_model_equal(result, expected)

    def test_ids_are_populated(self):
        """The canonical game id is set and the proton report references it."""
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = _insert_full_game(repo, proton_db_report=_make_report())

        assert isinstance(result.game.id, int) and result.game.id > 0
        assert result.deals, "expected at least one deal"
        assert result.proton_db_info is not None and result.proton_db_info.game_id > 0
        assert result.proton_db_info.game_id == result.game.id


class TestNoDeals:
    """Game without any deal data."""

    def test_deals_is_empty_list(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = _insert_full_game(repo, deals=[], proton_db_report=_make_report())

        assert result.deals == []
        assert result.proton_db_info is not None


class TestMissingProtonReport:
    """Game without a ProtonDB report."""

    def test_proton_db_info_is_none(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = _insert_full_game(repo, proton_db_report=None)

        assert result.deals
        assert result.proton_db_info is None


class TestDuplicateAppid:
    """Inserting the same (source, external_id) twice re-uses the game row."""

    def test_second_insert_reuses_game_id(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        first = _insert_full_game(repo, external_id="440", deals=[_make_deal()])
        second = _insert_full_game(
            repo, external_id="440", deals=[_make_deal(value_minor=499)]
        )

        # Same game row, two different cost observations
        assert second.game.id == first.game.id
        assert first.deals and second.deals
        assert second.deals[0].value_minor == 499
        assert first.deals[0].value_minor != second.deals[0].value_minor


class TestDifferentSources:
    """Same external_id on different sources creates different games."""

    def test_different_sources_yield_different_game_ids(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        steam = _insert_full_game(repo, external_id="123")
        itad = _insert_full_game(repo, external_id="123", game_source=GameSource.ITAD)

        assert steam.game.id != itad.game.id
        assert steam.game_source == GameSource.STEAM
        assert itad.game_source == GameSource.ITAD


class TestSourceNotFound:
    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        with pytest.raises(SourceNotFoundError, match="ITAD"):
            _insert_full_game(repo, game_source=GameSource.ITAD)


class TestProductType:
    def test_persists_dlc_product_type(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = _insert_full_game(
            repo, external_id="999", product_type=ProductType.DLC
        )

        assert result.game.product_type == ProductType.DLC


class TestInsertGame:
    """The lighter-weight ``insert_game`` creates a linked game row."""

    def test_returns_game_id_and_links_source(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        game_id = repo.get_or_insert_game(
            "Hollow Knight", ProductType.GAME, GameSource.STEAM, "367520"
        )

        assert isinstance(game_id, int) and game_id > 0
        assert repo.get_game_id_on_source(game_id, GameSource.STEAM) == "367520"

    def test_reuses_existing_game(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        first = repo.get_or_insert_game(
            "Hollow Knight", ProductType.GAME, GameSource.STEAM, "367520"
        )
        second = repo.get_or_insert_game(
            "Hollow Knight", ProductType.GAME, GameSource.STEAM, "367520"
        )

        assert first == second


class TestHistoricalLow:
    """``price_overview`` is persisted into the historical_low table."""

    def test_inserts_historical_low(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        pov = _make_price_overview(
            lowest_value_minor=500,
            country_l2="US",
            currency_3l="USD",
            scope=LowestPriceInPeriod.ALL,
        )
        result = _insert_full_game(repo, external_id="730", price_overview=pov)

        assert result.price_overview is pov

        with engine.begin() as conn:
            rows = conn.execute(historical_low_table.select()).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.game_id == result.game.id
        assert row.country_alpha2 == "US"
        assert row.currency == "USD"
        assert row.lowest_value_minor == 500
        assert row.scope.value == "all"

    def test_updates_historical_low(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        pov = _make_price_overview(
            lowest_value_minor=500,
            country_l2="US",
            currency_3l="USD",
            scope=LowestPriceInPeriod.ALL,
        )
        result = _insert_full_game(repo, external_id="730", price_overview=pov)

        pov = _make_price_overview(
            lowest_value_minor=100,
            country_l2="US",
            currency_3l="USD",
            scope=LowestPriceInPeriod.ALL,
        )
        result = _insert_full_game(repo, external_id="730", price_overview=pov)

        assert result.price_overview is pov

        with engine.begin() as conn:
            rows = conn.execute(historical_low_table.select()).fetchall()

        assert len(rows) == 1
        row = rows[0]
        assert row.game_id == result.game.id
        assert row.country_alpha2 == "US"
        assert row.currency == "USD"
        assert row.lowest_value_minor == 100
        assert row.scope.value == "all"


class TestAddGameSource:
    def test_links_game_to_source_external_id(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        # Create the game through the public repository API.
        sourced = _insert_full_game(repo, external_id="730")

        # Attach an additional (ITAD) source to the already-created game.
        repo.add_game_source(
            sourced.game.id, game_source=GameSource.ITAD, external_id="itad-123"
        )

        with engine.begin() as conn:
            itad_id = conn.execute(
                select(game_source_table.c.id).where(game_source_table.c.name == "ITAD")
            ).scalar_one()
            row = conn.execute(
                select(game_external_id_table).where(
                    game_external_id_table.c.game_id == sourced.game.id,
                    game_external_id_table.c.source_id == itad_id,
                )
            ).first()

        assert row is not None
        assert row.external_id == "itad-123"

    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameRepository(engine)
        sourced = _insert_full_game(repo, external_id="730")

        with pytest.raises(SourceNotFoundError, match="ITAD"):
            repo.add_game_source(
                sourced.game.id, game_source=GameSource.ITAD, external_id="x"
            )


class TestGetGameSource:
    def test_gets_source_when_exists(self):
        engine = _setup_engine()
        repo = GameRepository(engine)
        sourced = _insert_full_game(repo, external_id="730")
        external_id = repo.get_game_id_on_source(sourced.game.id, GameSource.STEAM)

        assert external_id == "730"

    def test_gets_source_when_multiple_sources_exist(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)
        sourced = _insert_full_game(repo, external_id="730")
        repo.add_game_source(
            sourced.game.id,
            game_source=GameSource.ITAD,
            external_id="itad-123",
        )
        external_id = repo.get_game_id_on_source(sourced.game.id, GameSource.STEAM)

        assert external_id == "730"

    def test_filters_by_game_id_not_just_source(self):
        """Regression: get_game_id_on_source must honor game_id, not only source_id."""
        engine = _setup_engine()
        repo = GameRepository(engine)

        steam_a = _insert_full_game(repo, external_id="730")
        steam_b = _insert_full_game(repo, external_id="999")

        ext_a = repo.get_game_id_on_source(steam_a.game.id, GameSource.STEAM)
        ext_b = repo.get_game_id_on_source(steam_b.game.id, GameSource.STEAM)

        assert ext_a == "730"
        assert ext_b == "999"
        assert ext_a != ext_b
