import asyncio
import logging
import traceback
from abc import ABC, abstractmethod

from steaminlinebot.game import core
from steaminlinebot.game.repository import IGameRepository
from steaminlinebot.integration import itad_client
from steaminlinebot.integration.itad_client import IITADClient
from steaminlinebot.integration.itad_mapper import (
    itad_deal_to_game_deal,
    itad_historical_low_to_historical_price_data,
)
from steaminlinebot.integration.steam_client import ISteamClient
from steaminlinebot.integration.steam_mapper import steam_cost_to_deal


class IGameSearcherService(ABC):
    """Searches game ids from a platform/store"""

    @abstractmethod
    async def search_game(
        self,
        query: str,
        country_2l: str,
    ) -> list[core.SourcedGame]: ...


async def _get_itad_overview_by_appid(
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
        country_2l: str,
    ):
        results: list[core.SourcedGame] = []
        appids = await self._client.search_game_title(query, country_2l)
        steam_results, itad_by_appid = await asyncio.gather(
            self._client.scrape_game_results(appids, country_2l),
            _get_itad_overview_by_appid(
                self._itad_client,
                [int(game.appid) for game in appids],
                country_2l,
            ),
        )

        for steam_game in steam_results.results:
            if steam_game.product_type.value not in _DESIRED_PRODUCT_TYPES:
                continue
            try:
                steam_deal = (
                    steam_cost_to_deal(steam_game.cost, steam_game.link)
                    if steam_game.cost is not None
                    else None
                )

                itad_overview = itad_by_appid.get(int(steam_game.appid))
                itad_deals = [
                    itad_deal_to_game_deal(deal, country_2l)
                    for deal in (itad_overview.deals if itad_overview else [])
                ]
                historical_price = (
                    itad_historical_low_to_historical_price_data(
                        itad_overview.historical_low, country_2l
                    )
                    if itad_overview is not None
                    else None
                )

                game_id, proton_db_info = self._game_repo.record_observation(
                    title=steam_game.title,
                    product_type=steam_game.product_type,
                    source=core.COMMON_GAME_SOURCE_NAMES.STEAM.value,
                    external_id=steam_game.appid,
                    deals=[d for d in (itad_deals + [steam_deal]) if d is not None],
                    historical_price=historical_price,
                    proton_report=steam_game.proton_db_report,
                )

                sourced_game = core.SourcedGame(
                    game=core.Game(
                        id=game_id,
                        title=steam_game.title,
                        product_type=steam_game.product_type,
                    ),
                    external_id=steam_game.appid,
                    game_source=core.COMMON_GAME_SOURCE_NAMES.STEAM,
                    main_deal=steam_deal,
                    other_deals=itad_deals,
                    url=steam_game.link,
                    price_overview=historical_price,
                    proton_db_info=proton_db_info,
                )
                results.append(sourced_game)
            except Exception as e:
                traceback.print_exc()
                logging.error(f"Error at search_game when building Result: {e}")

        return results


_DESIRED_PRODUCT_TYPES = set(["game", "dlc"])
