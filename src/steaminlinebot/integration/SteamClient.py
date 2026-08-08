import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Iterable, Optional, Union
from urllib.parse import urlencode

import aiohttp
from attr import dataclass
from bs4 import BeautifulSoup

from steaminlinebot.game.GameResult import ScrapedCost, ScrapedSteamGame
from steaminlinebot.integration.ProtonDBClient import IProtonDBClient
from steaminlinebot.integration.ProtonDBClient import (
    ProtonDBClient,
    ScrapedProtonDBReport,
)

# TODO: "https://store.steampowered.com/search/?term=" endpoint also offers the appid and game data
# which can be used to reduce the bot latency.


@dataclass
class ScrapeResult:
    found_error: Union[bool, Exception]
    results: list[ScrapedSteamGame]


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
    proton_db_report: Optional[ScrapedProtonDBReport] = None,
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

        if data["is_free"]:
            is_free = True
            cost = None
        elif "price_overview" not in data:
            cost = None
        else:
            overview = data["price_overview"]
            cost = ScrapedCost(
                value_minor=int(overview["final"]),
                currency_3l=overview["currency"],
                full_value_minor=int(overview["initial"]),
                discount=overview["discount_percent"],
                country_l2=country if country else "",
            )

        return ScrapedSteamGame(
            link=link,
            title=title,
            appid=appid,
            cost=cost,
            proton_db_report=proton_db_report,
            is_free=is_free,
            product_type=product_type,
        )

    except Exception as e:
        logging.warning(f"Error in _make_game_result: {e}")
        return None


class ISteamRequestMaker:
    async def get_many_game_details(self, appids, country) -> list[dict]: ...

    async def search_many_games_html(
        self, game_names: Iterable[str], country
    ) -> list[BeautifulSoup]: ...


class SteamRequestMaker(ISteamRequestMaker):
    _GAME_SEARCH_URL = "https://store.steampowered.com/search/suggest"
    _API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

    async def search_many_games_html(
        self, game_names: Iterable[str], country
    ) -> list[BeautifulSoup]:
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
                    f"Searching games URL: {self._GAME_SEARCH_URL}?{urlencode(params)}"
                )

                req = session.get(self._GAME_SEARCH_URL, params=params)
                tasks.append(req)

            responses = await asyncio.gather(*tasks)
            return [
                BeautifulSoup(await response.text(), "html.parser")
                for response in responses
            ]

    async def _get_game_details_json(
        self, appid, country, session: aiohttp.ClientSession
    ) -> dict:
        """makes steam api details request for given appid and returns future for it's json response"""
        params = {
            "appids": appid,
            "cc": country,
            "filters": "basic,price_overview",
        }
        logging.info(
            f"Getting game_details json: {self._API_APP_DETAILS_URL}?{urlencode(params)}"
        )
        # https://store.steampowered.com/api/appdetails?appids=730&cc=US&filters=basic,price_overview
        async with session.get(self._API_APP_DETAILS_URL, params=params) as r:
            return await r.json()

    # we need this only to get discount data, as _get_game_suggestions doesnt have it
    async def get_many_game_details(self, appids, country):
        async with aiohttp.ClientSession() as session:
            """gets game details for each given appid and returns list with every response's json"""
            tasks = [
                asyncio.create_task(
                    self._get_game_details_json(appid, country, session)
                )
                for appid in appids
            ]
            results = await asyncio.gather(*tasks)
            return results


def parse_many_appids(search_game_html_results: list[BeautifulSoup]):
    "analyzes html and returns dict of every appid found in the search for each given game name. empty keys (for now)"

    appids = {}
    for soup in search_game_html_results:
        for game in soup.find_all("a"):
            if game.has_attr("data-ds-appid"):
                appids[game["data-ds-appid"]] = ""
    return appids


class SteamClient(ISteamClient):
    def __init__(
        self,
        max_results: int,
        steam_request_maker: SteamRequestMaker,
        protondb_client: IProtonDBClient | None = None,
    ):
        self.max_results = max_results
        self._protondb = protondb_client or ProtonDBClient()
        self._steam_request_maker = steam_request_maker

    async def scrape_game_results(self, query: str, country: str) -> ScrapeResult:
        """gets game details for each appid found in the search for the given
        query(game name) and makes ScrapedGame obj from each of those and returns a list of them all
        """
        responses = await self._steam_request_maker.search_many_games_html(
            [query], country
        )
        appids = list(parse_many_appids(responses).keys())

        game_details, protondbs = await asyncio.gather(
            self._steam_request_maker.get_many_game_details(appids, country),
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
