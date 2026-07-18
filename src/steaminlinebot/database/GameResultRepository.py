import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.game.GameResult import GameResult
from steaminlinebot.user import Money
from steaminlinebot.integration.ProtonDBClient import ProtonDBReport, ProtonDBTier


class IGameResultRepository(ABC):
    """Data access for cached game results and ProtonDB reports."""

    @abstractmethod
    def insert_game_result(self, game: GameResult) -> int: ...

    @abstractmethod
    def get_game_result(self, gameresult_id: int) -> Optional[GameResult]: ...


class GameResultRepository(IGameResultRepository):
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert_game_result(self, game: GameResult) -> int:
        """
        Inserts a GameResult and optional ProtonDBReport.
        Returns the gameresults.id
        """
        with self.db:
            cur = self.db.execute(
                """
                INSERT INTO gameresults (
                    appid, link, price_minor, is_free, discount, date
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    game.appid,
                    game.link,
                    game.price.value_minor if game.price else None,
                    int(game.is_free),
                    game.discount,
                    int(time.time()),
                ),
            )

            game_id = cur.lastrowid
            assert game_id

            if game.proton_db_report:
                self._insert_protondb_report(game_id, game.proton_db_report)

            return game_id

    def _insert_protondb_report(
        self, gameresult_id: int, report: ProtonDBReport
    ) -> None:
        self.db.execute(
            """
            INSERT INTO protondbresults (
                id,
                bestReportedTier,
                confidence,
                score,
                tier,
                total,
                trendingTier
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gameresult_id,
                report.best_reported_tier,
                report.confidence,
                report.score,
                report.tier,
                report.total,
                report.trending_tier,
            ),
        )

    def get_game_result(self, gameresult_id: int) -> Optional[GameResult]:
        row = self.db.execute(
            """
            SELECT
                g.id, g.appid, g.link, g.price_minor, g.is_free, g.discount, g.date,g.country,
                p.bestReportedTier, p.confidence, p.score, p.tier, p.total, p.trendingTier, c.currency
            FROM gameresults g
            LEFT JOIN protondbresults p ON p.id = g.id
            LEFT JOIN countries c ON c.country = g.country
            WHERE g.id = ?
            """,
            (gameresult_id,),
        ).fetchone()

        if not row:
            return None

        (
            _id,
            appid,
            link,
            price_minor,
            is_free,
            discount,
            date,
            country,
            best_reported_tier,
            confidence,
            score,
            tier,
            total,
            trending_tier,
            currency,
        ) = row

        report = None
        if best_reported_tier is not None:
            report = ProtonDBReport(
                best_reported_tier=ProtonDBTier(int(best_reported_tier)),
                confidence=confidence,
                score=score,
                tier=ProtonDBTier(int(tier)),
                total=total,
                trending_tier=ProtonDBTier(int(trending_tier)),
            )

        price = Money.Money(
            country=country, currency3l=currency, value_minor=price_minor
        )

        return GameResult(
            appid=appid,
            link=link,
            title="",  # fill if you add it to DB later
            price=price,
            is_free=bool(is_free),
            discount=discount,
            proton_db_report=report,
            country=country,
        )
