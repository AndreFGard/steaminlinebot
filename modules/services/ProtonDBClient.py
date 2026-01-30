import asyncio
from collections import deque
from enum import IntEnum
import heapq
from dataclasses import dataclass
import logging
from typing import Any, Callable, Iterable, List, Tuple
import aiohttp
from functools import wraps
import time
from modules.async_lru_cache_ttl import async_lru_cache_ttl

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
    bestReportedTier: ProtonDBTier
    confidence: str
    score: float
    tier: ProtonDBTier
    total: int
    """Total number of reports"""
    trendingTier: ProtonDBTier
    def __repr__(self):
        return str(self.__dict__)


class ProtonDBClient:

    @staticmethod
    @async_lru_cache_ttl
    async def _getReport(appid: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
            ) as res:
                res.raise_for_status()
                data = await res.json()
                return ProtonDBReport(
                    bestReportedTier=ProtonDBTier[data["bestReportedTier"].upper()],
                    confidence=data["confidence"],
                    score=data["score"],
                    tier=ProtonDBTier[data["tier"].upper()],
                    total=data["total"],
                    trendingTier=ProtonDBTier[data["trendingTier"].upper()]
                )

    @staticmethod
    async def getReports(appids: Iterable[str]) -> list[None|ProtonDBReport]:
        results = await asyncio.gather(
            *(ProtonDBClient._getReport(appid) for appid in appids),
            return_exceptions=True,
        )

        filtered: list[None|ProtonDBReport] = [
            x if isinstance(x, ProtonDBReport) else None for x in results]
        
        for result,appid in filter(lambda x:isinstance(x[0], Exception), zip(results,appids)):
            logging.info(f"Error in protondb report of appid {appid}: {result}")
            
        return filtered
