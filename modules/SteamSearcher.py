from typing import Iterable, Optional, Union
from attr import dataclass
from gazpacho.soup import Soup
from modules import ProtonDB
from bs4 import BeautifulSoup
import aiohttp
import asyncio
from urllib.parse import quote_plus
import time

from modules.GameResult import GameResult
from modules.async_lru_cache_ttl import async_lru_cache_ttl
from urllib.parse import urlencode
import logging

API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}&cc=BR"


# WIP that uses the search endpoint rather than the appdetails one
async def _scrapSteam(query, MAX_RESULTS, cacheApp: dict = {}):
    results = []
    req_start_T = time.time()
    prefix = "https://store.steampowered.com/search/?term="
    if len(query) < 3:
        return
    query = quote_plus(query)  # Properly URI-encode the query string
    async with aiohttp.ClientSession() as session:
        async with session.get(prefix + query + "&cc=US") as response:
            page = await response.text()

    download_end = time.time()
    html = Soup(page)
    # filtering for data-ds-appids results in not showing bundles, requiring
    # appropriate filtering in the pricetags too, which is not implemented
    tags = html.find("a", {"data-ds-tagids": ""}, mode="all")

    if not tags:
        return []

    if not isinstance(tags, list):
        tags = [tags]

    for tag in tags[:MAX_RESULTS]:
        # Extract game data from tag - you need to implement the actual parsing logic
        # For now, this is a placeholder that needs to be replaced with actual scraping
        try:
            appid = tag.attrs.get("data-ds-appid", "")  # type:ignore
            if appid:
                # Fetch game details from API instead
                pass
        except:
            continue
    results_building_end = time.time()
    results_buinding_total = results_building_end - download_end
    req_t = download_end - req_start_T
    print(f"answer building total time: {req_t + results_buinding_total}:")
    print(f"\tpage download Time: {req_t}")
    results_building_end = time.time()
    return results


@dataclass
class ScrapeResult:
    found_error: Union[bool, Exception]
    results: list[GameResult]


class SteamSearcher:
    def __init__(self, MAX_RESULTS):
        self.MAX_RESULTS = MAX_RESULTS
        self.API_GAME_SEARCH = "https://store.steampowered.com/search/suggest"
        self.API_APP_DETAILS_URL = API_APP_DETAILS_URL

    async def _getGamesHtml(self, gamenames: Iterable[str]):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for gamename in gamenames:
                params = {
                    "term": (gamename),
                    "f": "games",
                    "cc": "BR",
                    "realm": 1,
                    "l": "english",
                }
                
                logging.info(f"Searching games URL: {self.API_GAME_SEARCH}?{urlencode(params)}")

                req = session.get(self.API_GAME_SEARCH, params=params)
                tasks.append(req)

            return await asyncio.gather(*tasks)

    @async_lru_cache_ttl
    async def getAppids(self, gamenames: Iterable[str]):
        "analyzes html and returns dict of every appid found in the search for each given game name. empty keys (for now)"
        responses = await self._getGamesHtml(gamenames)

        appids = {}
        for response in responses:
            html_content = await response.text()
            soup = BeautifulSoup(html_content, "html.parser")
            for l in soup.find_all("a"):
                if l.has_attr("data-ds-appid"):
                    appids[l["data-ds-appid"]] = ""
        return appids

    async def _getGameDetailsFromAppid(self, appid, session) -> dict:
        """makes steam api details request for given appid and returns future for it's json response"""
        async with session.get(self.API_APP_DETAILS_URL.format(appid)) as r:
            return await r.json()

    async def _getAllGameDetails(self, appids, session):
        """gets game details for each given appid and returns list with every response's json"""
        tasks = [
            asyncio.create_task(self._getGameDetailsFromAppid(appid, session))
            for appid in appids
        ]
        results = await asyncio.gather(*tasks)
        return results

    async def scrapeGameResults(self, query: str) -> ScrapeResult:
        """gets game details for each appid found in the search for the given
        query(game name) and makes GameResult obj from each of those and returns a list of them all
        """

        query = quote_plus(query)
        appids = tuple((await self.getAppids((query,))).keys())

        async with aiohttp.ClientSession() as session:
            gamedetails, protondbs = (
                await self._getAllGameDetails(appids, session),
                await ProtonDB.ProtonDBReportFactory.getReports(appids),
            )
            # hopefully, their order is the same

            raw_results = [
                GameResult.makeGameResultFromSteamApiGameDetails(
                    gameDetail, protonDBReport=protondb
                )
                for gameDetail, protondb in zip(gamedetails, protondbs)
            ]
            return ScrapeResult(
                (None in raw_results),
                [result for result in raw_results if result is not None],
            )


# debug
# searcher = SteamSearcher(6, {})
# results = searcher.getGameResultsSync("tarkov")
