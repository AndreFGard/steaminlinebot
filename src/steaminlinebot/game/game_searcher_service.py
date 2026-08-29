import asyncio
import logging
from abc import ABC, abstractmethod
import traceback
from typing import Optional


from steaminlinebot.database.game_repository import IGameRepository
from steaminlinebot.game import core
from steaminlinebot.game.core import (
    GameDeal,
    GameSource,
    HistoricalPriceData,
    LowestPriceInPeriod,
    ScrapedCost,
)
from steaminlinebot.integration import itad_client
from steaminlinebot.integration.itad_client import IITADClient
from steaminlinebot.integration.steam_client import ISteamClient



class IGameSearcherService(ABC):
    """Searches game ids from a platform/store"""

    @abstractmethod
    async def search_game(
        self,
        query: str,
        country_code: str,
    ) -> list[core.SourcedGame]: ...


async def _get_itad_prices(
    itad_client: itad_client.IITADClient, steam_appids: list[int], country_2l: str
) -> dict[int, itad_client.ITADPriceOverview | None]:
    """Map Steam app ids to their ITAD price overview (or None)."""
    itad_ids = await itad_client.lookup_by_steam_appid(steam_appids)
    requested = [game_id for game_id in itad_ids if game_id is not None]
    fetched = await itad_client.get_prices(requested, country_2l)

    by_id = dict(zip(requested, fetched))

    return {
        appid: (by_id.get(itad_id) if itad_id is not None else None)
        for appid, itad_id in zip(steam_appids, itad_ids)
    }


def _steam_cost_to_deal(cost: ScrapedCost) -> GameDeal:
    return GameDeal(
        value_minor=cost.value_minor,
        currency_3l=cost.currency_3l,
        full_value_minor=cost.full_value_minor,
        discount=cost.discount,
        country_l2=cost.country_l2,
        price_expires_at=None,
        observed_date=None,
        historical_deal=None,
    )


def _itad_overview_to_historical_price(
    price_overview: itad_client.ITADPriceOverview, country_2l: str
):
    return (
        HistoricalPriceData(
            scope=LowestPriceInPeriod.ALL,
            lowest_value_minor=price_overview.historical_low.all.amount_int,
            currency_3l=price_overview.historical_low.all.currency_3l,
            country_l2=country_2l,
        )
        if price_overview is not None and price_overview.historical_low.all is not None
        else None
    )


class GameSearchService(IGameSearcherService):
    def __init__(
        self,
        client: ISteamClient,
        game_repo: IGameRepository,
        itad_client: IITADClient,
    ):
        self._game_repo = game_repo
        self._client = client
        self._itad_client = itad_client

    async def search_game(
        self,
        query: str,
        country_code: str,
    ):
        results: list[core.SourcedGame] = []
        appids = await self._client.search_game_title(query, country_code)

        steam_results, itad_by_appid = await asyncio.gather(
            self._client.scrape_game_results(appids, country_code),
            _get_itad_prices(
                self._itad_client,
                [int(game.appid) for game in appids],
                country_code,
            ),
        )

        for game in steam_results.results:
            if game.product_type.value not in self._DESIRED_PRODUCT_TYPES:
                continue
            try:
                deals = (
                    [_steam_cost_to_deal(game.cost)] if game.cost is not None else []
                )
                itad_overview = itad_by_appid.get(int(game.appid))
                historical_price = (
                    _itad_overview_to_historical_price(itad_overview, country_code)
                    if itad_overview is not None
                    else None
                )

                game_result = self._game_repo.insert_full_game(
                    title=game.title,
                    product_type=game.product_type,
                    external_id=game.appid,
                    url=game.link,
                    deals=deals,
                    game_source=GameSource.STEAM,
                    price_overview=historical_price,
                    proton_db_report=game.proton_db_report,
                )

                results.append(game_result)
            except Exception as e:
                traceback.print_exc()
                logging.info(f"Error at search_game when building Result: {e}")

        return results

    _DESIRED_PRODUCT_TYPES = set(["game", "dlc"])
