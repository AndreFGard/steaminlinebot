import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from abc import ABC, abstractmethod
from typing import Optional

from babel.numbers import format_currency, get_currency_precision

from steaminlinebot.game.GameResultV2 import ScrapedSteamGame
from steaminlinebot.database.GameResultRepository import IGameResultRepository
from steaminlinebot.integration.ProtonDBClient import ProtonDBTier
from steaminlinebot.integration.SteamClient import ISteamClient
from steaminlinebot.user.UserCountry import IUserCountry


class ISearchGames(ABC):
    """Steam scraping + ProtonDB + persistence."""

    @abstractmethod
    async def search_game(
        self,
        user_id: int,
        query: str,
        fallback_languages: list[str] | None = None,
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


class SpecialResults(Enum):
    NO_MATCHES = 1
    ERROR = 2
    QUERY_TOO_SHORT = 4


@dataclass
class SearchResults:
    results: list[GameResultVM]
    special_results: list[SpecialResults]
    scrape_time: float
    configure_country: bool


def to_game_result_vm(result: ScrapedSteamGame, result_id: int) -> GameResultVM:
    """Pure function: maps a scraped Steam game + its persisted ID to the view model."""
    proton_db_vm = (
        ProtonDBVM(
            tier=result.proton_db_report.tier,
            positive_trend=result.proton_db_report.trending_tier
            > result.proton_db_report.tier,
            total_reports=result.proton_db_report.total,
            appid=result.appid,
        )
        if result.proton_db_report
        else None
    )

    if result.cost:
        price_str = format_currency(
            Decimal(result.cost.value_minor)
            / Decimal(10 ** get_currency_precision(result.cost.currency_3l)),
            result.cost.currency_3l,
        )
        discount = result.cost.discount
    else:
        price_str = None
        discount = None

    return GameResultVM(
        id=result_id,
        link=result.link,
        title=result.title,
        appid=result.appid,
        price=price_str,
        is_free=result.is_free,
        discount=discount,
        proton_db=proton_db_vm,
    )


class SearchGames(ISearchGames):
    def __init__(
        self,
        searcher: ISteamClient,
        game_result_repo: IGameResultRepository,
        user_country: IUserCountry,
    ):
        self._game_result_repo = game_result_repo
        self._searcher = searcher
        self._user_country = user_country

    async def search_game(self, user_id, query, fallback_languages=None):
        if fallback_languages is None:
            fallback_languages = []
        errors = set()
        results: list[GameResultVM] = []

        if len(query) < 3:
            errors.add(SpecialResults.QUERY_TOO_SHORT)
            return SearchResults(results, list(errors), 0.0, False)

        if not fallback_languages:
            fallback_languages.append("US")
        cfg = self._user_country.get_country(user_id, fallback_languages)
        country = cfg.country
        country_configured = cfg.has_configured

        start = time.time()
        res = await self._searcher.scrape_game_results(query, country)
        end = time.time()

        if res.found_error:
            errors.add(SpecialResults.ERROR)
        if not res.results:
            errors.add(SpecialResults.NO_MATCHES)

        for r in res.results:
            try:
                result_id = self._game_result_repo.insert_game_result(r)
                results.append(to_game_result_vm(r, result_id))
            except Exception as e:
                logging.info(f"Error at search_game when building Result: {e}")
                errors.add(SpecialResults.ERROR)

        return SearchResults(results, list(errors), end - start, not country_configured)
