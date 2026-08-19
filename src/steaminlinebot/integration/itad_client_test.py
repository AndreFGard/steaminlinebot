import asyncio
import os

import aiohttp

from steaminlinebot.integration import itad_client


# TODO Convert to fixture or just remove?
async def test_get_shop_map():
    async with aiohttp.ClientSession() as session:
        client = itad_client.ITADClient(os.environ["ITAD_KEY"], session)
        res = await client.get_shop_map()
        # validated by pydantic
        assert any(r.title == "Steam" for r in res)


async def test_lookup():
    async with aiohttp.ClientSession() as session:
        client = itad_client.ITADClient(os.environ["ITAD_KEY"], session)
        res = await client.lookup_by_steam_shopid(61, [489830, 2623190])
        print(res)
        # validated by pydantic
        assert res[489830] is not None


if __name__ == "__main__":
    asyncio.run(test_lookup())
