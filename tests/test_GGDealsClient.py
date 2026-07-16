import pytest
from unittest.mock import patch
from tests.aiohttp_mock import *
from modules.services.GGDealsClient import GGDealsAPI
@pytest.mark.asyncio
async def test_fetch_prices_success():
    payload = {
        "success": True,
        "data": {
            "489830": {
                "title": "Skyrim",
                "url": "https://example.com",
                "prices": {
                    "currentRetail": "10",
                    "currentKeyshops": None,
                    "historicalRetail": None,
                    "historicalKeyshops": None,
                    "currency": "USD"
                }
            }
        }
    }

    fake_response = FakeResponse(200, payload)

    with patch("aiohttp.ClientSession", return_value=FakeSession(fake_response)):
        api = GGDealsAPI("key")
        results = await api.searchAppids("us", ["489830"])

    assert results
    assert results[0].appid == "489830"
