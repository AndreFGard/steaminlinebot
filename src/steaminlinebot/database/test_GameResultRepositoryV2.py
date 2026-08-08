import pytest
from sqlalchemy import create_engine
import sqlalchemy
from steaminlinebot.database.schema import metadata, game_source_table, country_table
from steaminlinebot.database.GameResultRepositoryV2 import (
    GameResultRepository,
    SourceNotFoundError,
)
from steaminlinebot.game.GameResultV2 import (
    ScrapedSteamGame,
    ScrapedCost,
    GameResultV2,
    CostData,
    GameSourceInfo,
)
from steaminlinebot.game.ProtonDBReportV2 import ProtonDBReportV2, ProtonDBTier
from steaminlinebot.integration.ProtonDBClient import ScrapedProtonDBReport


# ===========================================================================
# Test helpers
# ===========================================================================


def _setup_engine() -> "sqlalchemy.Engine":
    """Create an in-memory SQLite engine pre-seeded with ``country`` and ``game_source``."""
    engine = create_engine("sqlite://")
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(country_table.insert().values(alpha2="US"))
        conn.execute(country_table.insert().values(alpha2="BR"))
        conn.execute(game_source_table.insert().values(name="Steam", itad_shop_id="61"))
        conn.execute(game_source_table.insert().values(name="GOG", itad_shop_id=None))
    return engine


def _make_game(
    *,
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
        product_type=product_type,
    )


def _make_cost(
    *,
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
    *,
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


# ---------------------------------------------------------------------------
# Comparison helper — strips ``id`` fields recursively from pydantic models
# (or plain dicts), then compares the remaining structure with plain ``==``.
# ---------------------------------------------------------------------------


# Keys stripped from models before comparison (auto-generated DB IDs)
_ID_KEYS = {"id", "game_id"}


def _strip_ids(obj):
    """Recursively remove auto-generated ID keys (``id``, ``game_id``, etc.)."""
    if hasattr(obj, "model_dump"):
        d = obj.model_dump()
    elif isinstance(obj, dict):
        d = obj
    else:
        return obj

    result: dict = {}
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


# ===========================================================================
# insert_game_result  tests
# ===========================================================================


class TestInsertFullGame:
    """Happy-path: game with cost + ProtonDB report."""

    def test_returns_correct_fields(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(
                cost=_make_cost(),
                proton_db_report=_make_report(),
            ),
            source_name="Steam",
        )

        expected = GameResultV2(
            id=0,  # stripped
            title="Counter-Strike",
            product_type="game",
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
            game_source=GameSourceInfo(
                source_name="Steam",
                external_id="730",
                itad_shop_id="61",
            ),
            proton_db_info=ProtonDBReportV2(
                game_id=0,
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
        """The top-level id, cost.id, and proton_db_info.game_id are set."""
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(
                cost=_make_cost(),
                proton_db_report=_make_report(),
            ),
            source_name="Steam",
        )

        assert isinstance(result.id, int) and result.id > 0
        assert result.cost is not None and result.cost.id > 0
        assert result.proton_db_info is not None and result.proton_db_info.game_id > 0
        assert result.proton_db_info.game_id == result.id


class TestFreeGame:
    """Game without cost data."""

    def test_cost_is_none(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(cost=None, proton_db_report=_make_report()),
            source_name="Steam",
        )

        assert result.cost is None
        assert result.proton_db_info is not None


class TestMissingProtonReport:
    """Game without a ProtonDB report."""

    def test_proton_db_info_is_none(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(cost=_make_cost(), proton_db_report=None),
            source_name="Steam",
        )

        assert result.cost is not None
        assert result.proton_db_info is None


class TestDuplicateAppid:
    """Inserting the same (source, appid) twice re-uses the game row."""

    def test_second_insert_reuses_game_id(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        first = repo.insert_game_result(
            _make_game(appid="440", cost=_make_cost()),
            source_name="Steam",
        )
        second = repo.insert_game_result(
            _make_game(appid="440", cost=_make_cost(value_minor=499)),
            source_name="Steam",
        )

        # Same game row, two different cost observations
        assert second.id == first.id
        assert second.cost is not None and second.cost.id != first.cost.id  # type: ignore[union-attr]
        assert second.cost.value_minor == 499  # type: ignore[union-attr]


class TestDifferentSources:
    """Same external_id on different sources creates different games."""

    def test_different_sources_yield_different_game_ids(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        steam = repo.insert_game_result(
            _make_game(appid="123", cost=_make_cost()),
            source_name="Steam",
        )
        gog = repo.insert_game_result(
            _make_game(appid="123", cost=_make_cost()),
            source_name="GOG",
        )

        assert steam.id != gog.id
        assert steam.game_source.source_name == "Steam"
        assert gog.game_source.source_name == "GOG"
        # GOG has no itad_shop_id
        assert gog.game_source.itad_shop_id is None


class TestSourceNotFound:
    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        with pytest.raises(SourceNotFoundError, match="NonExistentSource"):
            repo.insert_game_result(_make_game(), source_name="NonExistentSource")


class TestProductType:
    def test_persists_dlc_product_type(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(appid="999", product_type="dlc", cost=_make_cost()),
            source_name="Steam",
        )

        assert result.product_type == "dlc"
