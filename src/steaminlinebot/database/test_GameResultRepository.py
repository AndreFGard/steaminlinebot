from unittest.mock import MagicMock, patch

from steaminlinebot.database.GameResultRepository import GameResultRepository
from steaminlinebot.game.GameResult import GameResult
from steaminlinebot.integration.ProtonDBClient import ProtonDBReport, ProtonDBTier
from steaminlinebot.user.Money import Money


def _mock_db() -> MagicMock:
    return MagicMock()


def _make_game(
    *,
    appid: str = "730",
    link: str = "https://store.steampowered.com/app/730/",
    price: Money | None = None,
    is_free: bool = True,
    discount: int | None = None,
    country: str | None = "US",
    proton_db_report: ProtonDBReport | None = None,
) -> GameResult:
    return GameResult(
        appid=appid,
        link=link,
        title="",
        price=price,
        is_free=is_free,
        discount=discount,
        country=country,
        proton_db_report=proton_db_report,
    )


def _make_report(
    best_reported_tier: ProtonDBTier = ProtonDBTier.GOLD,
    confidence: str = "Strong",
    score: float = 0.9,
    tier: ProtonDBTier = ProtonDBTier.GOLD,
    total: int = 1500,
    trending_tier: ProtonDBTier = ProtonDBTier.PLATINUM,
) -> ProtonDBReport:
    return ProtonDBReport(
        best_reported_tier=best_reported_tier,
        confidence=confidence,
        score=score,
        tier=tier,
        total=total,
        trending_tier=trending_tier,
    )


class TestInsertGameResult:
    def test_returns_lastrowid(self):
        db = _mock_db()
        db.execute.return_value = MagicMock(lastrowid=42)

        repo = GameResultRepository(db)
        result = repo.insert_game_result(_make_game())

        assert result == 42

    def test_inserts_protondb_report_when_present(self):
        db = _mock_db()
        db.execute.return_value = MagicMock(lastrowid=10)
        report = _make_report()
        game = _make_game(proton_db_report=report)

        repo = GameResultRepository(db)
        with patch.object(repo, "_insert_protondb_report") as spy:
            result = repo.insert_game_result(game)

        assert result == 10
        spy.assert_called_once_with(10, report)

    def test_skips_protondb_report_when_none(self):
        db = _mock_db()
        db.execute.return_value = MagicMock(lastrowid=5)
        game = _make_game(proton_db_report=None)

        repo = GameResultRepository(db)
        with patch.object(repo, "_insert_protondb_report") as spy:
            repo.insert_game_result(game)

        spy.assert_not_called()


# Row tuples mirror the SELECT column order in get_game_result:
# (id, appid, link, price_minor, is_free, discount, date, country,
#  best_reported_tier, confidence, score, tier, total, trending_tier, currency)

_ROW_FULL = (
    1,
    "72850",
    "https://store.steampowered.com/app/72850/",
    999,
    0,
    50,
    1710800000,
    "US",
    4,
    "Strong",
    0.85,
    3,
    200,
    5,
    "USD",
)

_ROW_NO_PROTON = (
    2,
    "730",
    "https://store.steampowered.com/app/730/",
    None,
    1,
    None,
    1710800000,
    "US",
    None,
    None,
    None,
    None,
    None,
    None,
    "USD",
)

_ROW_NO_PRICE_NO_CURRENCY = (
    3,
    "99999",
    "https://store.steampowered.com/app/99999/",
    None,
    1,
    None,
    1710800000,
    "XX",
    None,
    None,
    None,
    None,
    None,
    None,
    None,
)


class TestGetGameResult:
    def test_returns_none_when_not_found(self):
        db = _mock_db()
        cur = MagicMock()
        cur.fetchone.return_value = None
        db.execute.return_value = cur

        repo = GameResultRepository(db)
        result = repo.get_game_result(999)

        assert result is None

    def test_constructs_full_game_result(self):
        db = _mock_db()
        cur = MagicMock()
        cur.fetchone.return_value = _ROW_FULL
        db.execute.return_value = cur

        repo = GameResultRepository(db)
        result = repo.get_game_result(1)

        expected = GameResult(
            appid="72850",
            link="https://store.steampowered.com/app/72850/",
            title="",
            price=Money(country="US", currency3l="USD", value_minor=999),
            is_free=False,
            discount=50,
            country="US",
            proton_db_report=ProtonDBReport(
                best_reported_tier=ProtonDBTier.GOLD,
                confidence="Strong",
                score=0.85,
                tier=ProtonDBTier.SILVER,
                total=200,
                trending_tier=ProtonDBTier.PLATINUM,
            ),
        )
        assert result == expected

    def test_handles_null_protondb_columns(self):
        db = _mock_db()
        cur = MagicMock()
        cur.fetchone.return_value = _ROW_NO_PROTON
        db.execute.return_value = cur

        repo = GameResultRepository(db)
        result = repo.get_game_result(2)

        expected = GameResult(
            appid="730",
            link="https://store.steampowered.com/app/730/",
            title="",
            price=None,
            is_free=True,
            discount=None,
            country="US",
            proton_db_report=None,
        )
        assert result == expected

    def test_handles_null_price_and_currency(self):
        db = _mock_db()
        cur = MagicMock()
        cur.fetchone.return_value = _ROW_NO_PRICE_NO_CURRENCY
        db.execute.return_value = cur

        repo = GameResultRepository(db)
        result = repo.get_game_result(3)

        expected = GameResult(
            appid="99999",
            link="https://store.steampowered.com/app/99999/",
            title="",
            price=None,
            is_free=True,
            discount=None,
            country="XX",
            proton_db_report=None,
        )
        assert result == expected
