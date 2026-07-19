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
# TODO: "https://store.steampowered.com/search/?term=" endpoint offers the appid and game data
# which can be used to reduce the bot latency.


@dataclass
class ScrapeResult:
    found_error: Union[bool, Exception]
    results: list[GameResult]


class ISteamClient(ABC):
    """Scrapes Steam search results and fetches game details."""

    @abstractmethod
    async def scrape_game_results(self, query: str, country: str) -> ScrapeResult: ...


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


def _make_game_result(
    game_details: dict,
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
            product_type=product_type,
        )

    except Exception as e:
        logging.warning(f"Error in _make_game_result: {e}")
        return None


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
                _make_game_result(
                    game_detail,
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
