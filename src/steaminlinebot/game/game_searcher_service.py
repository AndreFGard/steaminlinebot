import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.gameresult_repository import IGameResultRepository
from steaminlinebot.game import gameresult
from steaminlinebot.game.gameresult import ScrapedSteamGame
from steaminlinebot.game.protondb_report import ProtonDBTier
from steaminlinebot.integration.steam_client import ISteamClient


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


class IGameSearcherService(ABC):
    """Searches game ids from a platform/store"""

    @abstractmethod
    async def search_game(
        self,
        query: str,
        country_code: str,
    ) -> list[gameresult.GameResult]: ...


class GameSearchService(IGameSearcherService):
    def __init__(
        self,
        client: ISteamClient,
        game_result_repo: IGameResultRepository,
    ):
        self._game_result_repo = game_result_repo
        self._client = client

    def _insert_scraped_game(self, game: ScrapedSteamGame) -> gameresult.GameResult:
        return self._game_result_repo.insert_game_result(game, "Steam")

    async def search_game(
        self,
        query: str,
        country_code: str,
    ):
        results: list[gameresult.GameResult] = []
        appids = await self._client.search_game_title(query, country_code)
        res = await self._client.scrape_game_results(appids, country_code)

        for game in res.results:
            if game.product_type not in self._DESIRED_PRODUCT_TYPES:
                continue
            try:
                game_result = self._insert_scraped_game(game)
                results.append(game_result)
            except Exception as e:
                logging.info(f"Error at search_game when building Result: {e}")

        return results

    _DESIRED_PRODUCT_TYPES = set(["game", "dlc"])
