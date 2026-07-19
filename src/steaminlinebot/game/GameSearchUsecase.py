from dataclasses import dataclass

from steaminlinebot.game.SteamProvider import ISearchGames, SearchResults
from steaminlinebot.user.UserCountry import CountryConfig, IUserCountry


class QueryTooShortError(ValueError): ...


@dataclass
class GameSearchResult:
    search_results: SearchResults
    country_config: CountryConfig


class IGameSearchUsecase:
    async def handle_game_search(
        self, query: str, user_id: int, language_code: str
    ) -> GameSearchResult: ...


class GameSearchUsecase(IGameSearchUsecase):
    def __init__(
        self,
        user_country: IUserCountry,
        search_games: ISearchGames,
        default_country_code: str,
    ):
        self.user_country = user_country
        self.search_games = search_games
        self.default_country_code = default_country_code

    async def handle_game_search(
        self, query: str, user_id: int, language_code: str
    ) -> GameSearchResult:
        if len(query) < 3:
            raise QueryTooShortError(str(query))

        fallback_languages = [language_code, "en-us"]
        country_config = self.user_country.get_country(user_id, fallback_languages)

        search_results = await self.search_games.search_game(
            query, country_code=country_config.country or self.default_country_code
        )

        return GameSearchResult(
            search_results=search_results,
            country_config=country_config,
        )
