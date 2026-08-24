import pytest
from sqlalchemy import create_engine, select
import sqlalchemy
from typing import Optional

from steaminlinebot.database.schema import (
    country_table,
    game_external_id_table,
    game_source_table,
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
    ScrapedSteamGame,
    ScrapedCost,
    SourcedGame,
    CostData,
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


def _make_game(
    appid: str = "730",
    link: str = "https://store.steampowered.com/app/730/",
    title: str = "Counter-Strike",
    cost: ScrapedCost | None = None,
    is_free: bool = False,
    proton_db_report: ScrapedProtonDBReport | None = None,
    product_type: str = "game",
) -> ScrapedSteamGame:
    return ScrapedSteamGame(
        link=link,
        title=title,
        appid=appid,
        cost=cost,
        is_free=is_free,
        proton_db_report=proton_db_report,
        product_type=ProductType(product_type),
    )


def _make_cost(
    value_minor: int = 999,
    currency_3l: str = "USD",
    full_value_minor: int = 1999,
    discount: int = 50,
    country_l2: str = "US",
) -> ScrapedCost:
    return ScrapedCost(
        value_minor=value_minor,
        currency_3l=currency_3l,
        full_value_minor=full_value_minor,
        discount=discount,
        country_l2=country_l2,
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
    """Happy-path: game with cost + ProtonDB report."""

    def test_returns_correct_fields(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = repo.insert_game_result(
            _make_game(
                cost=_make_cost(),
                proton_db_report=_make_report(),
            ),
            game_source=GameSource.STEAM,
        )

        expected = SourcedGame(
            game=Game(id=0, title="Counter-Strike", product_type=ProductType.GAME),
            external_id="730",
            game_source=GameSource.STEAM,
            cost=CostData(
                id=0,  # stripped
                value_minor=999,
                currency_3l="USD",
                full_value_minor=1999,
                discount=50,
                country_l2="US",
                price_expires_at=None,
                observed_date=None,
                historical_deal=None,
            ),
            url="https://store.steampowered.com/app/730/",
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
        """The canonical game id, cost.id, and proton_db_info.game_id are set."""
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = repo.insert_game_result(
            _make_game(
                cost=_make_cost(),
                proton_db_report=_make_report(),
            ),
            game_source=GameSource.STEAM,
        )

        assert isinstance(result.game.id, int) and result.game.id > 0
        assert result.cost is not None and result.cost.id > 0
        assert result.proton_db_info is not None and result.proton_db_info.game_id > 0
        assert result.proton_db_info.game_id == result.game.id


class TestFreeGame:
    """Game without cost data."""

    def test_cost_is_none(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = repo.insert_game_result(
            _make_game(cost=None, proton_db_report=_make_report()),
            game_source=GameSource.STEAM,
        )

        assert result.cost is None
        assert result.proton_db_info is not None


class TestMissingProtonReport:
    """Game without a ProtonDB report."""

    def test_proton_db_info_is_none(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = repo.insert_game_result(
            _make_game(cost=_make_cost(), proton_db_report=None),
            game_source=GameSource.STEAM,
        )

        assert result.cost is not None
        assert result.proton_db_info is None


class TestDuplicateAppid:
    """Inserting the same (source, appid) twice re-uses the game row."""

    def test_second_insert_reuses_game_id(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        first = repo.insert_game_result(
            _make_game(appid="440", cost=_make_cost()),
            game_source=GameSource.STEAM,
        )
        second = repo.insert_game_result(
            _make_game(appid="440", cost=_make_cost(value_minor=499)),
            game_source=GameSource.STEAM,
        )

        # Same game row, two different cost observations
        assert second.game.id == first.game.id
        assert second.cost is not None and second.cost.id != first.cost.id  # type: ignore[union-attr]
        assert second.cost.value_minor == 499  # type: ignore[union-attr]


class TestDifferentSources:
    """Same external_id on different sources creates different games."""

    def test_different_sources_yield_different_game_ids(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        steam = repo.insert_game_result(
            _make_game(appid="123", cost=_make_cost()),
            game_source=GameSource.STEAM,
        )
        itad = repo.insert_game_result(
            _make_game(appid="123", cost=_make_cost()),
            game_source=GameSource.ITAD,
        )

        assert steam.game.id != itad.game.id
        assert steam.game_source == GameSource.STEAM
        assert itad.game_source == GameSource.ITAD


class TestSourceNotFound:
    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        with pytest.raises(SourceNotFoundError, match="ITAD"):
            repo.insert_game_result(_make_game(), game_source=GameSource.ITAD)


class TestProductType:
    def test_persists_dlc_product_type(self):
        engine = _setup_engine()
        repo = GameRepository(engine)

        result = repo.insert_game_result(
            _make_game(appid="999", product_type="dlc", cost=_make_cost()),
            game_source=GameSource.STEAM,
        )

        assert result.game.product_type == ProductType.DLC


class TestAddGameSource:
    def test_links_game_to_source_external_id(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)

        # Create the game through the public repository API.
        sourced = repo.insert_game_result(
            _make_game(appid="730"), game_source=GameSource.STEAM
        )

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
        sourced = repo.insert_game_result(
            _make_game(appid="730"), game_source=GameSource.STEAM
        )

        with pytest.raises(SourceNotFoundError, match="ITAD"):
            repo.add_game_source(
                sourced.game.id, game_source=GameSource.ITAD, external_id="x"
            )


class TestGetGameSource:
    def test_gets_source_when_exists(self):
        engine = _setup_engine()
        repo = GameRepository(engine)
        sourced = repo.insert_game_result(
            _make_game(appid="730"), game_source=GameSource.STEAM
        )
        external_id = repo.get_game_id_on_source(sourced.game.id, GameSource.STEAM)

        assert external_id == "730"

    def test_gets_source_when_multiple_sources_exist(self):
        engine = _setup_engine()
        _seed_source(engine, "ITAD")
        repo = GameRepository(engine)
        sourced = repo.insert_game_result(
            _make_game(appid="730"), game_source=GameSource.STEAM
        )
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

        steam_a = repo.insert_game_result(
            _make_game(appid="730"), game_source=GameSource.STEAM
        )
        steam_b = repo.insert_game_result(
            _make_game(appid="999"), game_source=GameSource.STEAM
        )

        ext_a = repo.get_game_id_on_source(steam_a.game.id, GameSource.STEAM)
        ext_b = repo.get_game_id_on_source(steam_b.game.id, GameSource.STEAM)

        assert ext_a == "730"
        assert ext_b == "999"
        assert ext_a != ext_b
