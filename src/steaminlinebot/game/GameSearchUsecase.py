from dataclasses import dataclass
from typing import Optional

from steaminlinebot.game import GameResult
from steaminlinebot.game.GameSearcher import (
    IGameSearcher,
)
from steaminlinebot.user.UserCountry import CountryConfig, IUserCountry


class QueryTooShortError(ValueError): ...


@dataclass
class GameSearchResult:
    search_results: list[GameResult.GameResult]
    country_config: CountryConfig


class IGameSearchUsecase:
    async def handle_game_search(
        self, query: str, user_id: int, user_lang_etf: Optional[str]
    ) -> GameSearchResult: ...


class GameSearchUsecase(IGameSearchUsecase):
    def __init__(
        self,
        user_country: IUserCountry,
        search_games: IGameSearcher,
    ):
        self.user_country = user_country
        self.search_games = search_games

    async def handle_game_search(
        self, query: str, user_id: int, user_lang_etf: Optional[str]
    ) -> GameSearchResult:
        if len(query) < 3:
            raise QueryTooShortError(str(query))

        country_config = await self.user_country.resolve_country(user_id, user_lang_etf)

        search_results = await self.search_games.search_game(
            query, country_code=country_config.country
        )

        return GameSearchResult(
            search_results=search_results,
            country_config=country_config,
        )
