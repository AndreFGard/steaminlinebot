import asyncio
import logging
from abc import ABC, abstractmethod
from urllib.parse import urlencode

import aiohttp
from attr import dataclass
from bs4 import BeautifulSoup
import pydantic

from steaminlinebot.game.core import ProductType
from steaminlinebot.integration.protondb_client import IProtonDBClient
from steaminlinebot.integration.protondb_client import (
    ProtonDBClient,
    ScrapedProtonDBReport,
)

# TODO: "https://store.steampowered.com/search/?term=" endpoint also offers the appid and game data
# which can be used to reduce the bot latency.


class SteamGame(pydantic.BaseModel):
    appid: int
    country_2l: str
    title: str | None

    # TODO: if I could detect a non-currency price, this could shortcircuit and avoid ITAD queries.
    _formatted_price: str | None


class SteamCost(pydantic.BaseModel):
    """Cost data from scraping"""

    value_minor: int
    currency_3l: str
    full_value_minor: int
    discount: int
    country_l2: str


class SteamDetailedGame(pydantic.BaseModel):
    """Steam scraping result"""

    link: str
    title: str
    appid: int
    cost: SteamCost | None
    is_free: bool
    proton_db_report: ScrapedProtonDBReport | None = None
    # TODO make enum
    product_type: ProductType


@dataclass
class ScrapeResult:
    found_error: bool | Exception
    results: list[SteamDetailedGame]


class ISteamClient(ABC):
    """Scrapes Steam search results and fetches game details."""

    @abstractmethod
    async def search_game_title(
        self, query: str, country_2l: str
    ) -> list[SteamGame]: ...
    @abstractmethod
    async def scrape_game_results(
        self, appids: list[SteamGame], country: str
    ) -> ScrapeResult: ...


def _make_game_result(
    game_details: dict,
    proton_db_report: ScrapedProtonDBReport | None = None,
    country: str | None = None,
):
    try:
        appid = int(list(game_details.keys())[0])

        if not game_details[str(appid)]["success"]:
            raise Exception(f"Unsuccessful game_details result: {game_details}")

        link = f"https://store.steampowered.com/app/{appid}/"
        data = game_details[str(appid)]["data"]
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
            cost = SteamCost(
                value_minor=int(overview["final"]),
                currency_3l=overview["currency"],
                full_value_minor=int(overview["initial"]),
                discount=overview["discount_percent"],
                country_l2=country if country else "",
            )

        return SteamDetailedGame(
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
    appid: int, country: str, session: aiohttp.ClientSession
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
    appids: list[int], country_2l, session: aiohttp.ClientSession
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
) -> list[SteamGame]:

    games = []
    for game in suggest_html_data.find_all("a"):
        if game.has_attr("data-ds-appid"):
            # suggest may return bundles/collections whose data-ds-appid is a
            # comma-separated list of appids, e.g. "219780,214170,219760"
            appids = str(game["data-ds-appid"]).split(",")

            price = game.find("div", attrs={"class": "match_price"})
            if price is not None:
                price = str(price)

            name = game.find("div", attrs={"class": "match_name"})
            if name is not None:
                name = str(name)

            for appid in appids:
                try:
                    parsed_appid = int(appid.strip())
                except ValueError:
                    logging.warning(f"Skipping non-numeric appid {appid!r}")
                    continue
                games.append(
                    SteamGame(
                        appid=parsed_appid,
                        title=name,
                        _formatted_price=price,
                        country_2l=country_2l,
                    )
                )
    # dedupe appids while preserving order (bundle entries can overlap)
    seen: set[str] = set()
    unique_games = []
    for game in games:
        if game.appid not in seen:
            seen.add(game.appid)
            unique_games.append(game)
    return unique_games


class SteamClient(ISteamClient):
    def __init__(
        self,
        session: aiohttp.ClientSession,
        protondb_client: IProtonDBClient | None = None,
    ):
        self._session = session
        self._protondb = protondb_client or ProtonDBClient()

    async def search_game_title(self, query: str, country_2l: str) -> list[SteamGame]:
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
        self, appids: list[SteamGame], country: str
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
