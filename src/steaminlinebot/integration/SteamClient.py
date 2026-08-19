import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Union
from urllib.parse import urlencode

import aiohttp
from attr import dataclass
from bs4 import BeautifulSoup
import pydantic

from steaminlinebot.game.GameResult import ScrapedCost, ScrapedSteamGame
from steaminlinebot.integration.ProtonDBClient import IProtonDBClient
from steaminlinebot.integration.ProtonDBClient import (
    ProtonDBClient,
    ScrapedProtonDBReport,
)

# TODO: "https://store.steampowered.com/search/?term=" endpoint also offers the appid and game data
# which can be used to reduce the bot latency.


class GameAppid(pydantic.BaseModel):
    appid: str
    country_2l: str

    _title: Optional[str]
    _formatted_price: Optional[str]


@dataclass
class ScrapeResult:
    found_error: Union[bool, Exception]
    results: list[ScrapedSteamGame]


class ISteamClient(ABC):
    """Scrapes Steam search results and fetches game details."""

    @abstractmethod
    async def search_game_title(
        self, query: str, country_2l: str
    ) -> list[GameAppid]: ...
    @abstractmethod
    async def scrape_game_results(
        self, appids: list[GameAppid], country: str
    ) -> ScrapeResult: ...


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


_API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"


async def _get_game_details_json(
    appid, country, session: aiohttp.ClientSession
) -> dict:
    """makes steam api details request for given appid and returns future for it's json response"""
    params = {
        "appids": appid,
        "cc": country,
        "filters": "basic,price_overview",
    }
    logging.info(
        f"Getting game_details json: {_API_APP_DETAILS_URL}?{urlencode(params)}"
    )
    # https://store.steampowered.com/api/appdetails?appids=730&cc=US&filters=basic,price_overview
    async with session.get(_API_APP_DETAILS_URL, params=params) as r:
        return await r.json()


# we need this only to get discount data, as _get_game_suggestions doesnt have it
async def _get_many_game_details(
    appids: list[str], country_2l, session: aiohttp.ClientSession
) -> list[dict]:
    """gets game details for each given appid and returns list with every response's json"""
    tasks = [
        asyncio.create_task(_get_game_details_json(appid, country_2l, session))
        for appid in appids
    ]
    results = await asyncio.gather(*tasks)
    return results


def parse_game_appids_from_suggest_html(
    suggest_html_data: BeautifulSoup, country_2l: str
) -> list[GameAppid]:

    games = []
    for game in suggest_html_data.find_all("a"):
        if game.has_attr("data-ds-appid"):
            appid = str(game["data-ds-appid"])

            price = game.find("div", attrs={"class": "match_price"})
            if price is not None:
                price = str(price)

            name = game.find("div", attrs={"class": "match_name"})
            if name is not None:
                name = str(name)

            games.append(
                GameAppid(
                    appid=appid,
                    _title=name,
                    _formatted_price=price,
                    country_2l=country_2l,
                )
            )
    return games


class SteamClient(ISteamClient):
    def __init__(
        self,
        session: aiohttp.ClientSession,
        protondb_client: IProtonDBClient | None = None,
    ):
        self._session = session
        self._protondb = protondb_client or ProtonDBClient()

    async def search_game_title(self, query: str, country_2l: str) -> list[GameAppid]:
        # This was the endpoint used as you typed in the steam search bar. Now unused by the steam store.
        _GAME_SEARCH_SUGGEST_URL = "https://store.steampowered.com/search/suggest"

        params = {
            "term": (query),
            "f": "games",
            "cc": country_2l,
            "realm": 1,
            "l": "english",
        }
        # https://store.steampowered.com/search/suggest?term=counter+strike&f=games&cc=US&realm=1&l=english
        logging.info(
            f"Searching games URL: {_GAME_SEARCH_SUGGEST_URL}?{urlencode(params)}"
        )

        req = self._session.get(_GAME_SEARCH_SUGGEST_URL, params=params)
        res = await req
        data = BeautifulSoup(await res.text(), "html.parser")

        appids = parse_game_appids_from_suggest_html(data, country_2l)
        return appids

    async def scrape_game_results(
        self, appids: list[GameAppid], country: str
    ) -> ScrapeResult:
        """gets game details for each appid found in the search for the given
        query(game name) and makes ScrapedGame obj from each of those and returns a list of them all
        """

        game_details, protondbs = await asyncio.gather(
            _get_many_game_details(
                [game.appid for game in appids], country, self._session
            ),
            self._protondb.get_reports([game.appid for game in appids]),
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
