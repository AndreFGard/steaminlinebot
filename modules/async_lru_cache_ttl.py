from typing import List, Callable, Tuple, Any
import heapq
import time
import asyncio
from functools import wraps


def async_lru_cache_ttl(f: Callable, maxsize=5000, delta_s=60*60*48):
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
