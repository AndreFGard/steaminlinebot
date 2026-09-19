from dataclasses import dataclass

from steaminlinebot.game.core import SourcedGame
from steaminlinebot.game.game_searcher_service import (
    IGameSearcherService,
)
from steaminlinebot.user.user_country import CountryConfig, IUserCountry


class QueryTooShortError(ValueError): ...


@dataclass
class GameSearchResult:
    search_results: list[SourcedGame]
    country_config: CountryConfig


class IGameSearchUsecase:
    async def handle_game_search(
        self, query: str, user_id: int, user_lang_etf: str | None
    ) -> GameSearchResult: ...


class GameSearchUsecase(IGameSearchUsecase):
    def __init__(
        self,
        user_country: IUserCountry,
        search_games: IGameSearcherService,
    ):
        self._user_country = user_country
        self._search_games = search_games

    async def handle_game_search(
        self, query: str, user_id: int, user_lang_etf: str | None
    ) -> GameSearchResult:

        country_config = None

        # @steaminlinebot /US Game
        first, _, rest = query.partition(" ")
        if first.startswith("/"):
            country_str = first[1:].upper()
            if await self._user_country.is_valid_country(country_str):
                country_config = CountryConfig(country=country_str, has_configured=True)
                query = rest.strip()

        if len(query) < 3:
            raise QueryTooShortError(str(query))

        if country_config is None:
            country_config = await self._user_country.resolve_country(
                user_id, user_lang_etf
            )

        search_results = await self._search_games.search_game(
            query, country_2l=country_config.country
        )

        return GameSearchResult(
            search_results=search_results,
            country_config=country_config,
        )
