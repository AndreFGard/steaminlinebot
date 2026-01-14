import asyncio
from collections import deque
import heapq
from dataclasses import dataclass
import logging
from typing import Any, Callable, Iterable, List, Tuple
import aiohttp
from functools import wraps
import time

def lru_cache_ttl(f: Callable, maxsize=5000, delta_s=60*60*48):
    cache: dict[Tuple, Tuple[float, float, Any]] = {}
    heap: List[Tuple[float, Tuple]] = []
    lock = asyncio.Lock()

    @wraps(f)
    async def ff(*args, **kwargs):
        key = args + tuple(sorted(kwargs.items()))
        curtime = time.monotonic()

        async with lock:
            if key in cache:
                created, last_access, value = cache[key]
                if curtime - created <= delta_s:
                    cache[key] = (created, curtime, value)
                    heapq.heappush(heap, (curtime, key))
                    return value
                else:
                    cache.pop(key)

        val = await f(*args, **kwargs)
        curtime = time.monotonic()

        async with lock:
            while len(cache) >= maxsize:
                access, k = heapq.heappop(heap)
                if k in cache and access == cache[k][1]:
                    cache.pop(k)

            cache[key] = (curtime, curtime, val)
            heapq.heappush(heap, (curtime, key))

        return val

    return ff

            


@dataclass
class ProtonDBReport:
    bestReportedTier: str
    confidence: str
    score: float
    tier: str
    total: int
    trendingTier: str

class ProtonDBReportFactory:
    @staticmethod
    @lru_cache_ttl
    async def _getReport(appid: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json"
            ) as res:
                res.raise_for_status()
                return ProtonDBReport(**(await res.json()))

    @staticmethod
    async def getReports(appids: Iterable[str]) -> list[None|ProtonDBReport]:
        results = await asyncio.gather(
            *(ProtonDBReportFactory._getReport(appid) for appid in appids),
            return_exceptions=True,
        )

        filtered: list[None|ProtonDBReport] = [
            x if isinstance(x, ProtonDBReport) else None for x in results]
        
        for appid,r in filter(lambda x:isinstance(x[0], Exception), zip(results,appids)):
            logging.info(f"Error in protondb report of appid {appid} {r}")
            
        return filtered
