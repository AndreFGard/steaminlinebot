import asyncio
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Iterable

import aiohttp

from steaminlinebot.game.protondb_report import ProtonDBTier
from steaminlinebot.utils.async_lru_cache_ttl import async_lru_cache_ttl


class IProtonDBClient(ABC):
    """Fetches ProtonDB compatibility reports for Steam app IDs."""

    @abstractmethod
    async def get_reports(
        self, appids: Iterable[str]
    ) -> list[None | ScrapedProtonDBReport]: ...


@dataclass
class ScrapedProtonDBReport:
    best_reported_tier: ProtonDBTier
    confidence: str
    score: float
    tier: ProtonDBTier
    total: int
    """Total number of reports"""
    trending_tier: ProtonDBTier

    def __repr__(self):
        return str(self.__dict__)


@async_lru_cache_ttl
async def _get_report(appid: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
        ) as res:
            res.raise_for_status()
            data = await res.json()
            return ScrapedProtonDBReport(
                best_reported_tier=ProtonDBTier[data["bestReportedTier"].upper()],
                confidence=data["confidence"],
                score=data["score"],
                tier=ProtonDBTier[data["tier"].upper()],
                total=data["total"],
                trending_tier=ProtonDBTier[data["trendingTier"].upper()],
            )


class ProtonDBClient(IProtonDBClient):
    async def get_reports(
        self, appids: Iterable[str]
    ) -> list[None | ScrapedProtonDBReport]:
        results = await asyncio.gather(
            *(_get_report(appid) for appid in appids),
            return_exceptions=True,
        )

        filtered: list[None | ScrapedProtonDBReport] = [
            x if isinstance(x, ScrapedProtonDBReport) else None for x in results
        ]

        for result, appid in (
            x for x in zip(results, appids) if isinstance(x[0], Exception)
        ):
            logging.info(f"Error in protondb report of appid {appid}: {result}")

        return filtered
