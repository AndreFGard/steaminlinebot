import datetime

from steaminlinebot.game import core
from steaminlinebot.integration import itad_client


def itad_historical_low_to_historical_price_data(
    historical_low: itad_client.ITADHistoricalLowInfo, country_2l: str
) -> core.HistoricalPriceData | None:
    return (
        core.HistoricalPriceData(
            scope=core.LowestPriceInPeriod.ALL,
            lowest_value_minor=historical_low.all.amount_int,
            currency_3l=historical_low.all.currency_3l,
            country_l2=country_2l,
        )
        if historical_low.all is not None
        else None
    )


def itad_deal_to_game_deal(
    deal: itad_client.ITADDeal, country_2l: str
) -> core.GameDeal:
    return core.GameDeal(
        value_minor=deal.price.amount_int,
        currency_3l=deal.price.currency_3l,
        full_value_minor=deal.regular.amount_int,
        discount=deal.cut,
        country_l2=country_2l,
        historical_deal=None,
        observed_date=datetime.datetime.now(),
        price_expires_at=deal.expiry,
        url=deal.url,
        source_shop=deal.shop.name,
    )
