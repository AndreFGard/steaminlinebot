import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Union
from urllib.parse import quote_plus, urlencode

import aiohttp
from attr import dataclass
from bs4 import BeautifulSoup
from gazpacho.soup import Soup

from steaminlinebot.game.GameResult import GameResult
from steaminlinebot.utils.async_lru_cache_ttl import async_lru_cache_ttl
from steaminlinebot.user.Money import Money
from steaminlinebot.integration.ProtonDBClient import IProtonDBClient
from steaminlinebot.integration.ProtonDBClient import ProtonDBClient, ProtonDBReport

API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


# WIP that uses the search endpoint rather than the appdetails one
async def _scrap_steam(query, max_results, cache_app: dict = {}):
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

    for tag in tags[:max_results]:
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


class ISteamClient(ABC):
    """Scrapes Steam search results and fetches game details."""

    @abstractmethod
    async def scrape_game_results(self, query: str, country: str) -> ScrapeResult: ...


class SteamClient(ISteamClient):
    def __init__(
        self,
        max_results: int,
        protondb_client: IProtonDBClient | None = None,
    ):
        self.max_results = max_results
        self.api_game_search = "https://store.steampowered.com/search/suggest"
        self.api_app_details_url = API_APP_DETAILS_URL
        self._protondb = protondb_client or ProtonDBClient()

    @staticmethod
    def _parse_discount(price_str, discount_value: int):
        """Parses discounts in different locales"""
        e = Exception()
        for valueidx in [0, 1]:
            try:
                if float(price_str.split()[valueidx].replace(",", ".")) == 0.0:
                    return None
                else:
                    if float(discount_value) == 0.0:
                        return None
                    discount = f"-{discount_value:.0f}%"
                    return discount
            except Exception as ee:
                e = ee
        logging.warning(
            f"Price parsing of price/discount: ('{price_str}','{discount_value}') error: {e}"
        )
        return None

    @staticmethod
    def _make_game_result(
        game_details: dict,
        desired_type: str,
        proton_db_report: Optional[ProtonDBReport] = None,
        country: Optional[str] = None,
    ):
        try:
            appid: str = tuple(game_details.keys())[0]

            if not game_details[appid]["success"]:
                raise Exception(f"Unsuccessful game_details result: {game_details}")

            link = f"https://store.steampowered.com/app/{appid}/"
            data = game_details[appid]["data"]
            title = data["name"]
            product_type = data["type"]
            if product_type != desired_type:
                raise Exception(f"Undesired Game type {product_type}")

            has_price = False
            is_free = False
            discount = None

            if data["is_free"]:
                is_free = True
                money = None
            elif "price_overview" not in data:
                money = None
                discount = None
            else:
                # This is a WIP, as the value position changes based on locales/countries
                currency = data["price_overview"]["currency"]
                discount = data["price_overview"]["discount_percent"]
                money = Money(
                    country=country if country else "",
                    currency3l=currency,
                    value_minor=int(data["price_overview"]["final"]),
                )

            return GameResult(
                link=link,
                title=title,
                appid=appid,
                price=money,
                discount=discount,
                proton_db_report=proton_db_report,
                is_free=is_free,
                country=country,
            )

        except Exception as e:
            logging.warning(f"Error in _make_game_result: {e}")
            return None

    async def _get_game_suggestions(self, game_names: Iterable[str], country):
        async with aiohttp.ClientSession() as session:
            tasks = []
            for game_name in game_names:
                params = {
                    "term": (game_name),
                    "f": "games",
                    "cc": country,
                    "realm": 1,
                    "l": "english",
                }
                # https://store.steampowered.com/search/suggest?term=counter+strike&f=games&cc=US&realm=1&l=english
                logging.info(
                    f"Searching games URL: {self.api_game_search}?{urlencode(params)}"
                )

                req = session.get(self.api_game_search, params=params)
                tasks.append(req)

            return await asyncio.gather(*tasks)

    @async_lru_cache_ttl
    async def get_app_ids(self, game_names: Iterable[str], country):
        "analyzes html and returns dict of every appid found in the search for each given game name. empty keys (for now)"
        responses = await self._get_game_suggestions(game_names, country)

        appids = {}
        for response in responses:
            html_content = await response.text()
            soup = BeautifulSoup(html_content, "html.parser")
            for l in soup.find_all("a"):
                if l.has_attr("data-ds-appid"):
                    appids[l["data-ds-appid"]] = ""
        return appids

    async def _get_game_details_from_app_id(self, appid, country, session) -> dict:
        """makes steam api details request for given appid and returns future for it's json response"""
        params = {
            "appids": appid,
            "cc": country,
            "filters": "basic,price_overview",
        }
        logging.info(
            f"Getting game_details json: {self.api_app_details_url}?{urlencode(params)}"
        )
        # https://store.steampowered.com/api/appdetails?appids=730&cc=US&filters=basic,price_overview
        async with session.get(self.api_app_details_url, params=params) as r:
            return await r.json()

    # we need this only to get discount data, as _get_game_suggestions doesnt have it
    async def _get_all_game_details(self, appids, country, session):
        """gets game details for each given appid and returns list with every response's json"""
        tasks = [
            asyncio.create_task(
                self._get_game_details_from_app_id(appid, country, session)
            )
            for appid in appids
        ]
        results = await asyncio.gather(*tasks)
        return results

    async def scrape_game_results(self, query: str, country: str) -> ScrapeResult:
        """gets game details for each appid found in the search for the given
        query(game name) and makes GameResult obj from each of those and returns a list of them all
        """

        appids = tuple((await self.get_app_ids((query,), country)).keys())

        async with aiohttp.ClientSession() as session:
            game_details, protondbs = await asyncio.gather(
                self._get_all_game_details(appids, country, session),
                self._protondb.get_reports(appids),
            )
            # hopefully, their order is the same

            raw_results = [
                SteamClient._make_game_result(
                    game_detail,
                    desired_type="game",
                    proton_db_report=protondb,
                    country=country,
                )
                for game_detail, protondb in zip(game_details, protondbs)
            ]
            return ScrapeResult(
                (None in raw_results),
                [result for result in raw_results if result is not None],
            )


# debug
# searcher = SteamClient(6, {})
# results = searcher.getGameResultsSync("tarkov")
