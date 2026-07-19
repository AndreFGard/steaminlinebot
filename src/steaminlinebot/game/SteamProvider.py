import logging
import time
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.GameResultRepository import IGameResultRepository
from steaminlinebot.integration.ProtonDBClient import ProtonDBTier
from steaminlinebot.integration.SteamClient import ISteamClient


class ISearchGames(ABC):
    """Orchestrates game search: Steam scraping + ProtonDB + persistence."""

    @abstractmethod
    async def search_game(
        self,
        query: str,
        country_code: str,
    ) -> SearchResults: ...


@dataclass
class ProtonDBVM:
    tier: ProtonDBTier
    positive_trend: bool
    total_reports: int
    appid: str


@dataclass
class GameResultVM:
    """View Model"""

    id: int
    link: str
    title: str
    appid: str
    price: Optional[str]
    is_free: bool
    discount: Optional[int]
    proton_db: Optional[ProtonDBVM]


@dataclass
class SearchResults:
    results: list[GameResultVM]
    scrape_time: float


class SteamProvider(ISearchGames):
    def __init__(
        self,
        client: ISteamClient,
        game_result_repo: IGameResultRepository,
    ):
        self._game_result_repo = game_result_repo
        self._client = client

    async def search_game(
        self,
        query: str,
        country_code: str,
    ):
        results: list[GameResultVM] = []

        start = time.time()
        res = await self._client.scrape_game_results(query, country_code)
        end = time.time()

        for r in res.results:
            if r.product_type != "game":
                continue

            try:
                result_id = self._game_result_repo.insert_game_result(r)

                proton_db_vm = (
                    ProtonDBVM(
                        tier=r.proton_db_report.tier,
                        positive_trend=r.proton_db_report.trending_tier
                        > r.proton_db_report.tier,
                        total_reports=r.proton_db_report.total,
                        appid=r.appid,
                    )
                    if r.proton_db_report
                    else None
                )

                results.append(
                    GameResultVM(
                        id=result_id,
                        link=r.link,
                        title=r.title,
                        appid=r.appid,
                        price=r.price.present() if r.price else None,
                        is_free=r.is_free,
                        discount=r.discount,
                        proton_db=proton_db_vm,
                    )
                )
            except Exception as e:
                logging.info(f"Error at search_game when building Result: {e}")

        return SearchResults(results, end - start)
