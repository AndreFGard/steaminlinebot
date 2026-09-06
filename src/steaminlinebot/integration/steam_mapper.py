from steaminlinebot.game import core


def steam_cost_to_deal(cost: core.ScrapedCost, url: str) -> core.GameDeal:
    return core.GameDeal(
        value_minor=cost.value_minor,
        currency_3l=cost.currency_3l,
        full_value_minor=cost.full_value_minor,
        discount=cost.discount,
        country_l2=cost.country_l2,
        price_expires_at=None,
        observed_date=None,
        historical_deal=None,
        url=url,
        source_shop=core.COMMON_GAME_SOURCE_NAMES.STEAM.value,
    )
