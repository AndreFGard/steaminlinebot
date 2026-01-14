import asyncio
from collections import deque
import heapq
from dataclasses import dataclass
import logging
from typing import Any, Callable, Iterable, List, Tuple
import aiohttp
from functools import wraps
import time
 
from modules.async_lru_cache_ttl import async_lru_cache_ttl
from modules.ProtonDBReport import ProtonDBReport
            


class ProtonDBReportFactory:
    @staticmethod
    @async_lru_cache_ttl
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
