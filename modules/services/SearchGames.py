import logging
from sqlite3 import Connection

from dataclasses import dataclass
import time

from modules.SteamSearcher import SteamSearcher
from modules.db.UserRepository import UserRepository
from modules.db.GameResultRepository import GameResultRepository
from typing import Optional
from pydantic import BaseModel
from modules.ProtonDBReport import ProtonDBReport, ProtonDBTier
from modules.services.UserCountry import UserCountry
@dataclass
class ProtonDBVM:
    tier: ProtonDBTier
    positive_trend: bool
    totalReports: int
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
    discount: Optional[str]
    protonDB: Optional[ProtonDBVM]

from enum import Enum

class SpecialResults(Enum):
    NO_MATCHES = 1
    ERROR = 2
    QUERY_TOO_SHORT = 4

@dataclass
class SearchResults:
    results: list[GameResultVM]
    specialResults: list[SpecialResults]
    scrapeTime: float
    configureCountry: bool


class SearchGames:
    def __init__(self, db:Connection):
        self._db = db
        self._userRepo = UserRepository(db)
        self._gameResultRepo = GameResultRepository(db)
        self._searcher = SteamSearcher(MAX_RESULTS=6)
        self._userCountry = UserCountry(db)
    async def searchGame(self, userId, query, fallback_languages=[]):
        errors = set()
        results = []

        if len(query) < 3:
            errors.add(SpecialResults.QUERY_TOO_SHORT)
            return SearchResults(results, list(errors), 0.0, False)
        
        if not fallback_languages: fallback_languages.append("US")
        cfg = self._userCountry.get_country(userId,fallback_languages)
        country = cfg.country
        country_configured = cfg.hasConfigured

        start = time.time()
        res = await self._searcher.scrapeGameResults(query, country)
        end = time.time()

        if res.found_error:
            errors.add(SpecialResults.ERROR)
        if not res.results:
            errors.add(SpecialResults.NO_MATCHES)
        
        for r in res.results:
            try:
                rId = self._gameResultRepo.insert_game_result(r)

                protonDBVm = (ProtonDBVM(
                    tier= r.protonDBReport.tier,
                    positive_trend=r.protonDBReport.trendingTier > r.protonDBReport.tier,
                    totalReports=r.protonDBReport.total,
                    appid=r.appid)
                        if r.protonDBReport else None)

                results.append(GameResultVM(
                    id=rId,
                    link=r.link,
                    title=r.title,
                    appid=r.appid,
                    price=r.price,
                    is_free=r.is_free,
                    discount=r.discount,
                    protonDB=protonDBVm
                ))
            except Exception as e:
                logging.info(f"Error at searchGame when building Result: {e}")
                errors.add(SpecialResults.ERROR)

        return SearchResults(results, list(errors), end-start, not country_configured)