import logging
import sqlite3
import time
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.game.GameResultV2 import ScrapedSteamGame
from steaminlinebot.game.ProtonDBReportV2 import ProtonDBTier
from steaminlinebot.integration.ProtonDBClient import (
    ScrapedProtonDBReport,
)


class IGameResultRepository(ABC):
    """Data access for cached game results and ProtonDB reports."""

    @abstractmethod
    def insert_game_result(self, game: ScrapedSteamGame) -> int: ...

    @abstractmethod
    def get_game_result(self, gameresult_id: int) -> Optional[ScrapedSteamGame]: ...


class GameResultRepository(IGameResultRepository):
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def insert_game_result(self, game: ScrapedSteamGame) -> int:
        """
        Inserts a ScrapedSteamGame and optional ProtonDBReport.
        Returns the gameresults.id
        """
        with self.db:
            cur = self.db.execute(
                """
                INSERT INTO gameresults (
                    appid, link, price_minor, is_free, discount, date, country
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    game.appid,
                    game.link,
                    game.cost.value_minor if game.cost else None,
                    int(game.is_free),
                    game.cost.discount if game.cost else None,
                    int(time.time()),
                    game.cost.country_l2 if game.cost else None,
                ),
            )

            game_id = cur.lastrowid
            assert game_id

            if game.proton_db_report:
                self._insert_protondb_report(game_id, game.proton_db_report)

            return game_id

    def _insert_protondb_report(
        self, gameresult_id: int, report: ScrapedProtonDBReport
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

    def get_game_result(self, gameresult_id: int) -> Optional[ScrapedSteamGame]:
        row = self.db.execute(
            """
            SELECT
                g.id, g.appid, g.link, g.price_minor, g.is_free, g.discount, g.date, g.country,
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
            report = ScrapedProtonDBReport(
                best_reported_tier=ProtonDBTier(int(best_reported_tier)),
                confidence=confidence,
                score=score,
                tier=ProtonDBTier(int(tier)),
                total=total,
                trending_tier=ProtonDBTier(int(trending_tier)),
            )

        cost = None
        if price_minor is not None and currency:
            from steaminlinebot.game.GameResultV2 import ScrapedCost

            cost = ScrapedCost(
                value_minor=price_minor,
                currency_3l=currency,
                full_value_minor=price_minor,  # approximated, not stored separately
                discount=discount or 0,
                country_l2=country or "",
            )

        return ScrapedSteamGame(
            appid=appid,
            link=link,
            title="",  # not stored in DB yet
            cost=cost,
            is_free=bool(is_free),
            proton_db_report=report,
        )
