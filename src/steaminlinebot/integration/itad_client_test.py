import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from steaminlinebot.integration.itad_client import (
    ITADClient,
    ITADDealFlag,
    ITADGameId,
)

_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "fixtures"

_LOOKUP_FIXTURE = "itad_lookup_by_steam_skyrim_kenshi.json"
_PRICES_FIXTURE = "itad_pricesv3_skyrim_kenshi.json"

_LOOKUP_URL = "https://api.isthereanydeal.com/lookup/id/shop/61/v1"
_PRICES_URL = "https://api.isthereanydeal.com/games/prices/v3"

# Anonymized stand-ins for the real Skyrim/Kenshi ids used in the fixtures.
_SKYRIM_STEAM_ID = 489830
_KENSHI_STEAM_ID = 233860
_SKYRIM_ITAD_ID = "0190a1b2-c3d4-5e6f-7a8b-9c0d1e2f3a4b"
_KENSHI_ITAD_ID = "0190a1b2-c3d4-5e6f-7a8b-9c0d1e2f3a5c"


def _load_fixture(name: str):
    with open(_FIXTURE_DIR / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def responses():
    return {
        _LOOKUP_URL: _load_fixture(_LOOKUP_FIXTURE),
        _PRICES_URL: _load_fixture(_PRICES_FIXTURE),
    }


@pytest.fixture
def session(responses):
    async def _post(url, **kwargs):
        return SimpleNamespace(
            status=200,
            json=AsyncMock(return_value=responses[str(url)]),
            text=AsyncMock(return_value=""),
        )

    sess = MagicMock()
    sess.post = AsyncMock(side_effect=_post)
    return sess


@pytest.fixture
def itad_client(session):
    return ITADClient("fake-itad-key", 61, session)


async def test_lookup_by_steam_appid_maps_and_orders(itad_client, session):
    result = await itad_client.lookup_by_steam_appid([_SKYRIM_STEAM_ID, _KENSHI_STEAM_ID])

    assert result == [
        ITADGameId(_SKYRIM_ITAD_ID),
        ITADGameId(_KENSHI_ITAD_ID),
    ]

    args, kwargs = session.post.await_args
    assert str(args[0]) == _LOOKUP_URL
    assert kwargs["json"] == [f"app/{_SKYRIM_STEAM_ID}", f"app/{_KENSHI_STEAM_ID}"]
    assert kwargs["headers"]["ITAD-API-Key"] == "fake-itad-key"


async def test_get_prices_returns_overviews_in_request_order(itad_client, session):
    game_ids = [
        _SKYRIM_ITAD_ID,  # Skyrim
        _KENSHI_ITAD_ID,  # Kenshi
    ]

    result = await itad_client.get_prices(game_ids, "US")

    assert [overview.id for overview in result] == game_ids

    args, kwargs = session.post.await_args
    assert str(args[0]) == _PRICES_URL
    assert kwargs["json"] == game_ids
    assert kwargs["params"] == {"country": "US"}
    assert kwargs["headers"]["ITAD-API-Key"] == "fake-itad-key"


async def test_get_prices_parses_nested_fields(itad_client):
    skyrim_id = _SKYRIM_ITAD_ID
    kenshi_id = _KENSHI_ITAD_ID

    skyrim, kenshi = await itad_client.get_prices([skyrim_id, kenshi_id], "US")

    assert skyrim.historical_low.all is not None
    assert skyrim.historical_low.all.amount == pytest.approx(8.07)
    assert skyrim.historical_low.all.currency_3l == "USD"

    steam_deal = next(deal for deal in skyrim.deals if deal.shop.id == 61)
    assert steam_deal.deal_flag is None

    humble = next(deal for deal in kenshi.deals if deal.shop.name == "Humble Store")
    assert humble.deal_flag == ITADDealFlag.StoreLow
