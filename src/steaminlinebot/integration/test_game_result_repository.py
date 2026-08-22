import pytest
from sqlalchemy import create_engine, select
import sqlalchemy
from steaminlinebot.database.schema import (
    country_table,
    game_external_id_table,
    game_source_table,
    metadata,
)
from steaminlinebot.database.gameresult_repository import (
    GameResultRepository,
    SourceNotFoundError,
)
from steaminlinebot.game.gameresult import (
    ScrapedSteamGame,
    ScrapedCost,
    GameResult,
    CostData,
    GameSourceInfo,
)
from steaminlinebot.game.protondb_report import ProtonDBReport, ProtonDBTier
from steaminlinebot.integration.protondb_client import ScrapedProtonDBReport


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


# Keys stripped from models before comparison


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
        repo = GameResultRepository(engine)

        result = repo.insert_game_result(
            _make_game(
                cost=_make_cost(),
                proton_db_report=_make_report(),
            ),
            source_name="Steam",
        )

        expected = GameResult(
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
            proton_db_info=ProtonDBReport(
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


class TestAddGameSource:
    def test_links_game_to_source_external_id(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)

        # Create the game through the public repository API.
        game = repo.insert_game_result(_make_game(appid="730"), source_name="Steam")

        # Attach an additional (GOG) source to the already-created game.
        repo.add_game_source(
            game.id,
            GameSourceInfo(source_name="GOG", external_id="gog-123", itad_shop_id=None),
        )

        with engine.begin() as conn:
            gog_id = conn.execute(
                select(game_source_table.c.id).where(game_source_table.c.name == "GOG")
            ).scalar_one()
            row = conn.execute(
                select(game_external_id_table).where(
                    game_external_id_table.c.game_id == game.id,
                    game_external_id_table.c.source_id == gog_id,
                )
            ).first()

        assert row is not None
        assert row.external_id == "gog-123"

    def test_raises_when_source_missing(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)
        game = repo.insert_game_result(_make_game(appid="730"), source_name="Steam")

        with pytest.raises(SourceNotFoundError, match="NoSuchSource"):
            repo.add_game_source(
                game.id,
                GameSourceInfo(
                    source_name="NoSuchSource", external_id="x", itad_shop_id=None
                ),
            )

class TestGetGameSource:
    def test_gets_source_when_exists(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)
        game = repo.insert_game_result(_make_game(appid="730"), source_name="Steam")
        source_info = repo.get_source_info(game.id, "Steam")
        
        assert source_info is not None
        assert source_info.source_name == "Steam"
        assert source_info.external_id == "730"

    def test_gets_source_when_multiple_sources_exist(self):
        engine = _setup_engine()
        repo = GameResultRepository(engine)
        game = repo.insert_game_result(_make_game(appid="730"), source_name="Steam")
        repo.add_game_source(
                game.id,
                GameSourceInfo(
                    source_name="GPG", external_id="x", itad_shop_id=None
                ),
            )
        source_info = repo.get_source_info(game.id, "Steam")
        
        assert source_info is not None
        assert source_info.source_name == "Steam"
        assert source_info.external_id == "730"