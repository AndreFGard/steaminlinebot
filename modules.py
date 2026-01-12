import json
from typing import Iterable, Optional
import gazpacho
from gazpacho.soup import Soup
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import uuid4


API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}&cc=BR"
ERROR_RESULT=InlineQueryResultArticle(id=str(uuid4()),
                title="Error",description=("Error: Sorry. Please report this with the /report command so we can fix it."),
                input_message_content=InputTextMessageContent(parse_mode="Markdown",
                message_text=("Error: Something has gone wrong here. Please report this with the /report command so I can fix it."),),)



def digitsToEmoji(digit: str):
    emojis = ("0⃣", "1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣")
    answer = ""
    for d in digit:
        answer += emojis[int(d)]    
    return answer

def discountToEmoji(discount: str):
    return digitsToEmoji(discount[1:-1])

class GameResult:
    def __init__(self, link:str, title:str, appid:str,itad_plain:str,price:float,discount:Optional[str], cacheStorage: dict = {}, price_formatted :int = False):
        self.link = link
        self.link = link
        self.title = title
        self.appid = appid
        self.itad_plain = itad_plain
        self.discount = discount
        self.price = price

    @staticmethod
    def makeGameResultFromSteamApiGameDetails( gamedetails:dict,cacheStorage: dict ={}):
        try:
            appid: str = tuple(gamedetails.keys())[0]
            if gamedetails[appid]['success']:
                data = gamedetails[appid]['data']
                title = data['name']
                link = f"https://store.steampowered.com/app/{appid}/"
                itad_plain = cacheStorage[appid] if appid in cacheStorage else "not found"
                price = 0.0
                if data['is_free'] or 'price_overview' not in data:
                    price = 0.0
                    discount = None
                else:
                    price = data['price_overview']['final_formatted']
                    discountAmount = float(str(data['price_overview']['discount_percent']))
                    discount = f"-{discountAmount:.2f}%" if discountAmount > 0 else ''
                print(f"{title}: {price} - {appid}")
                return(GameResult(link, title, appid, itad_plain, price, discount, cacheStorage))
        except Exception as e:
            print(f"Error in makeGameResultFromSteamApiGameDetails: {e}")
            return None

import time
async def scrapSteam(query, MAX_RESULTS, cacheApp: dict ={}):
    results = []
    req_start_T = time.time()
    prefix = "https://store.steampowered.com/search/?term="
    if len(query) < 3:
        return
    query = query.replace(' ', '+') #necessary for queries with spaces to work
    async with aiohttp.ClientSession() as session:
                async with session.get(prefix + query + "&cc=US") as response:
                    page = await response.text()

    download_end = time.time()
    html = Soup(page)
    #filtering for data-ds-appids results in not showing bundles, requiring
    # appropriate filtering in the pricetags too, which is not implemented
    tags = html.find("a", {"data-ds-tagids": ""}, mode="all")
    
    if not tags:
        return []
    
    if not isinstance(tags, list):
        tags = [tags]

    for tag in tags[:MAX_RESULTS]:
        # Extract game data from tag - you need to implement the actual parsing logic
        # For now, this is a placeholder that needs to be replaced with actual scraping
        try:
            appid = tag.attrs.get('data-ds-appid', '') #type:ignore
            if appid:
                # Fetch game details from API instead
                pass
        except:
            continue
    results_building_end = time.time()    
    results_buinding_total = results_building_end - download_end 
    req_t =  download_end - req_start_T 
    print(f"answer building total time: {req_t + results_buinding_total}:")
    print(f"\tpage download Time: {req_t}")
    results_building_end = time.time()
    return results


def makeInlineQueryResultArticle(result: GameResult):
    try: 
        return InlineQueryResultArticle(
                id=str(uuid4()),
                title=result.title,
                description=f"Price: {result.price}" + (f"   [{result.discount}]" if result.discount else  ""),
                thumbnail_url=f"https://cdn.akamai.steamstatic.com/steam/apps/{result.appid}/capsule_sm_120.jpg?t",  #low qual thumb
                # description=description,
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    #message_text=f"[{result.title}]({result.link})\nPrice:{result.price_formatted}" + (f"\nDiscount: -{discountToEmoji(result.discount)}%" if result.discount else ""), #https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg? can be used in order to not show the game's description
                    message_text=f"[{result.title}]({result.link})\nPrice: *{result.price}*" + (f"   [{result.discount}]" if result.discount else  "")
                ),
                reply_markup=InlineKeyboardMarkup(
                    (
                       (
                            InlineKeyboardButton("Steam Page", url=result.link),
                            InlineKeyboardButton("ProtonDB 🐧",url=f"https://www.protondb.com/app/{result.appid}"),
                        ),
                        [InlineKeyboardButton("Historico de preços", url=f"https://isthereanydeal.com/game/{result.itad_plain}/info/")], #creates a button in its own line, bellow the buttons above
                    )
                ),
            )
    except Exception as e:
        print("error in makeInlineQueryResultArticle: {e}")




from bs4 import BeautifulSoup
import aiohttp
import asyncio
class SteamSearcher:
    def __init__(self, MAX_RESULTS):
        self.API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}&cc=BR"
        self.MAX_RESULTS = MAX_RESULTS
        self.API_GAME_SEARCH = "https://store.steampowered.com/search/suggest?term={}&f=games&cc=BR&realm=1&l=english"
    
    async def searchGames(self, gamenames: Iterable[str]):
        """returns html containing the search for each given game name"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            for gamename in gamenames:
                tasks.append((session.get(self.API_GAME_SEARCH.format(gamename))))
            return await asyncio.gather(*tasks)

    async def getAppids(self, gamenames: Iterable[str]):
        "analyzes html and returns dict of every appid found in the search for each given game name. empty keys (for now)"
        responses = await self.searchGames(gamenames)
        appids = {}
        for response in responses:
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            for l in soup.find_all('a'):
                if l.has_attr("data-ds-appid"):
                    appids[l["data-ds-appid"]] = ""
        return appids

    async def getGameDetailsFromAppid(self, appid, session) -> dict:
        """makes steam api details request for given appid and returns future for it's json response"""
        async with session.get(self.API_APP_DETAILS_URL.format(appid)) as r:
            return await r.json()

    async def getAllGameDetails(self, appids, session):
        """gets game details for each given appid and returns list with every response's json"""
        tasks =[asyncio.create_task(self.getGameDetailsFromAppid(appid, session)) for appid in appids]
        results = await asyncio.gather(*tasks)
        return results

    async def makeGameResultsFromGameDetails(self, query:str) -> list[GameResult]:
        """gets game details for each appid found in the search for the given
          query(game name) and makes GameResult obj from each of those and returns a list of them all"""
        appids = tuple((await self.getAppids((query,))).keys())

        async with aiohttp.ClientSession() as session:
            data = tuple(GameResult.makeGameResultFromSteamApiGameDetails(gameDetail)
                          for gameDetail in (await self.getAllGameDetails(appids, session)))
            if None in data:
                data = tuple(i for i in data if i is not None) + (ERROR_RESULT, ) 
            return data


#debug
# searcher = SteamSearcher(6, {})
# results = searcher.getGameResultsSync("tarkov")