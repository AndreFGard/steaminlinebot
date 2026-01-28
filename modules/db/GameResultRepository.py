import sqlite3
import logging
from typing import Optional
from modules.GameResult import GameResult
from modules.ProtonDBReport import ProtonDBReport, ProtonDBTier
import time 

class GameResultRepository:
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
                    appid, link, price, is_free, discount, date
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    game.appid,
                    game.link,
                    game.price,
                    int(game.is_free),
                    game.discount,
                    int(time.time()),
                ),
            )

            game_id = cur.lastrowid
            assert game_id

            if game.protonDBReport:
                self._insert_protondb_report(game_id, game.protonDBReport)

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
                report.bestReportedTier,
                report.confidence,
                report.score,
                report.tier,
                report.total,
                report.trendingTier,
            ),
        )

    def get_game_result(self, gameresult_id: int) -> Optional[GameResult]:
        row = self.db.execute(
            """
            SELECT
                g.id, g.appid, g.link, g.price, g.is_free, g.discount, g.date,g.country,
                p.bestReportedTier, p.confidence, p.score, p.tier, p.total, p.trendingTier
            FROM gameresults g
            LEFT JOIN protondbresults p ON p.id = g.id
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
            price,
            is_free,
            discount,
            date,
            country,
            bestReportedTier,
            confidence,
            score,
            tier,
            total,
            trendingTier,
        ) = row

        report = None
        if bestReportedTier is not None:
            report = ProtonDBReport(
                bestReportedTier=ProtonDBTier(int(bestReportedTier)),
                confidence=confidence,
                score=score,
                tier=ProtonDBTier(int(tier)),
                total=total,
                trendingTier=ProtonDBTier(int(trendingTier)),
            )

        return GameResult(
            appid=appid,
            link=link,
            title="",  # fill if you add it to DB later
            price=price,
            is_free=bool(is_free),
            discount=discount,
            protonDBReport=report,
            country=country
        )
