import logging
import time
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Optional

from steaminlinebot.database.GameResultRepositoryV2 import IGameResultRepositoryV2
from steaminlinebot.game import GameResultV2
from steaminlinebot.game.GameResultV2 import ScrapedSteamGame
from steaminlinebot.game.ProtonDBReportV2 import ProtonDBTier
from steaminlinebot.integration.SteamClient import ISteamClient


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


# TODO this does not belong here as it's not steam specific
def _gameresult_to_gameresultvm(game: GameResultV2.GameResultV2) -> GameResultVM:
    # TODO see what code will be responsible for price formatting
    price = (
        None
        if not game.cost
        else f"{game.cost.value_minor} {game.cost.currency_3l} ({game.cost.country_l2})"
    )

    if game.proton_db_info:
        proton_vm = ProtonDBVM(
            tier=game.proton_db_info.tier,
            positive_trend=False,
            total_reports=game.proton_db_info.total,
            appid=game.game_source.external_id,
        )
    else:
        proton_vm = None

    return GameResultVM(
        id=game.id,
        link=game.url,
        title=game.title,
        appid=game.game_source.external_id,
        price=price,
        is_free=game.cost.full_value_minor == 0 if game.cost else False,
        discount=game.cost.discount if game.cost else None,
        proton_db=proton_vm,
    )


class ISearchGames(ABC):
    """Orchestrates game search: Steam scraping + ProtonDB + persistence."""

    @abstractmethod
    async def search_game(
        self,
        query: str,
        country_code: str,
    ) -> SearchResults: ...


@dataclass
class SearchResults:
    results: list[GameResultVM]
    scrape_time: float


class SteamProvider(ISearchGames):
    def __init__(
        self,
        client: ISteamClient,
        game_result_repo: IGameResultRepositoryV2,
    ):
        self._game_result_repo = game_result_repo
        self._client = client

    def _insert_scraped_game(self, game: ScrapedSteamGame) -> GameResultV2.GameResultV2:
        return self._game_result_repo.insert_game_result(game, "Steam")

    async def search_game(
        self,
        query: str,
        country_code: str,
    ):
        results: list[GameResultVM] = []

        start = time.time()
        res = await self._client.scrape_game_results(query, country_code)
        end = time.time()

        for game in res.results:
            if game.product_type not in self._DESIRED_PRODUCT_TYPES:
                continue
            try:
                game_vm = _gameresult_to_gameresultvm(self._insert_scraped_game(game))
                results.append(game_vm)
            except Exception as e:
                logging.info(f"Error at search_game when building Result: {e}")

        return SearchResults(results, end - start)

    _DESIRED_PRODUCT_TYPES = set(["game", "dlc"])
