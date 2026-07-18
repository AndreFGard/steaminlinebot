import asyncio
import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from functools import wraps
from abc import ABC, abstractmethod
from typing import Any, Callable, Iterable, List, Tuple

import aiohttp

from steaminlinebot.utils.async_lru_cache_ttl import async_lru_cache_ttl


class IProtonDBClient(ABC):
    """Fetches ProtonDB compatibility reports for Steam app IDs."""

    @abstractmethod
    async def get_reports(
        self, appids: Iterable[str]
    ) -> list[None | ProtonDBReport]: ...


class ProtonDBTier(IntEnum):
    BORKED = 1
    BRONZE = 2
    SILVER = 3
    GOLD = 4
    PLATINUM = 5

    def label(self):
        return self.name.lower().capitalize()

    def __str__(self):
        return self.label()

    def to_emoji(self):
        return {
            "GOLD": "✔️(4/5)",
            "SILVER": "✔️(3/5)",
            "BRONZE": "🟡(2/5)",
            "PLATINUM": "✅(5/5)",
            "BORKED": "❌ (1/5)",
        }[self.name]

    @classmethod
    def from_int(cls, tier: int):
        return cls(tier)


@dataclass
class ProtonDBReport:
    best_reported_tier: ProtonDBTier
    confidence: str
    score: float
    tier: ProtonDBTier
    total: int
    """Total number of reports"""
    trending_tier: ProtonDBTier

    def __repr__(self):
        return str(self.__dict__)


class ProtonDBClient(IProtonDBClient):
    @staticmethod
    @async_lru_cache_ttl
    async def _get_report(appid: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
            ) as res:
                res.raise_for_status()
                data = await res.json()
                return ProtonDBReport(
                    best_reported_tier=ProtonDBTier[data["bestReportedTier"].upper()],
                    confidence=data["confidence"],
                    score=data["score"],
                    tier=ProtonDBTier[data["tier"].upper()],
                    total=data["total"],
                    trending_tier=ProtonDBTier[data["trendingTier"].upper()],
                )

    async def get_reports(self, appids: Iterable[str]) -> list[None | ProtonDBReport]:
        results = await asyncio.gather(
            *(ProtonDBClient._get_report(appid) for appid in appids),
            return_exceptions=True,
        )

        filtered: list[None | ProtonDBReport] = [
            x if isinstance(x, ProtonDBReport) else None for x in results
        ]

        for result, appid in filter(
            lambda x: isinstance(x[0], Exception), zip(results, appids)
        ):
            logging.info(f"Error in protondb report of appid {appid}: {result}")

        return filtered
