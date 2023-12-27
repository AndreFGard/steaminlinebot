import json
import gazpacho
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import uuid4


API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}"



class cachev0:
    """Contains a map between steam appids and is there any deal yet plains"""
    def __init__(self, jsonFileName: str):
        self.storage = {}
        self.changesToWrite = False
        if jsonFileName != "":
            with open(jsonFileName, "r") as f:
                self.storage = json.load(f)
        else:
            self.storage = dict()

def digitsToEmoji(digit: str):
    emojis = ("0⃣", "1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣")
    answer = ""
    for d in digit:
        answer += emojis[int(d)]    
    return answer

def discountToEmoji(discount: str):
    return digitsToEmoji(discount[1:-1])



class GameResult:
    def __init__(self, link:str, title:str, appid:str,itad_plain:str,price:float,discount:str, cacheStorage: dict):
        self.link = link
        self.link = link
        self.title = title
        self.appid = appid
        self.itad_plain = itad_plain
        self.price = price
        self.discount = discount

    def makeGameResultFromTag(tag: list[gazpacho.Soup], cacheStorage: dict):
        """Game found with the search and it's informations"""
        link = tag.attrs["href"] if "href" in tag.attrs else ""
        title = tag.text
        #if appid is not in there, it's a bundle.
        appid = tag.attrs["data-ds-appid"] if "data-ds-appid" in tag.attrs else tag.attrs["data-ds-bundleid"]
        itad_plain = cacheStorage[appid] if appid in cacheStorage else "not found"

        pricetag = tag.find("div", {"class": "col search_price_discount_combined responsive_secondrow"}, mode="first")
        price = int(pricetag.attrs["data-price-final"]) * 0.01
        discount = pricetag.text if pricetag.text.startswith("-") else ""
        return(GameResult(link, title, appid, itad_plain, price, discount, cacheStorage))
    
    def makeGameResultFromSteamApiGameDetails(gamedetails:dict,cacheStorage: dict ={}):
        if gamedetails:
            appid: str = tuple(gamedetails.keys())[0]
            if gamedetails[appid]['success']:
                data = gamedetails[appid]['data']
                title = data['name']
                link = f"https://store.steampowered.com/app/{appid}/"
                itad_plain = cacheStorage[appid] if appid in cacheStorage else "not found"
                if data['is_free'] or 'price_overview' not in data:
                    price = 0.0
                    discount = False
                else:
                    price = data['price_overview']['final_formatted'] 
                    discount = discount = "-" + str(data['price_overview']['discount_percent']) + "%"
                return(GameResult(link, title, appid, itad_plain, price, discount, cacheStorage))
        return False

import time
from gazpacho import get, Soup
def scrapSteam(query, MAX_RESULTS, cacheApp: dict ={}):
    results = []
    req_start_T = time.time()
    prefix = "https://store.steampowered.com/search/?term="
    if len(query) < 3:
        return
    query = query.replace(' ', '+') #necessary for queries with spaces to work
    try:
        page = get(prefix + query + "&cc=BR") #&cc=BR makes the search use Brazilian regional pricing
    except Exception as e:
        return [False]
        logger.error(e)
        return
    download_end = time.time()
    html = Soup(page)
    #filtering for data-ds-appids results in not showing bundles, requiring
    # appropriate filtering in the pricetags too, which is not implemented
    tags = html.find("a", {"data-ds-tagids": ""}, mode="all")
    tag_start_t = time.time()

    for tag,i in zip(tags, range(MAX_RESULTS)):
        gameResult = GameResult.makeGameResultFromTag(tag, cacheApp.storage)
        results.append(makeInlineQueryResultArticle(gameResult))
    results_building_end = time.time()    
    results_buinding_total = results_building_end - download_end 
    req_t =  download_end - req_start_T 
    print(f"answer building total time: {req_t + results_buinding_total}:")
    print(f"\tpage download Time: {req_t}")
    results_building_end = time.time()
    return results

from bs4 import BeautifulSoup
import aiohttp
import asyncio
def makeInlineQueryResultArticle(result: GameResult):
    return InlineQueryResultArticle(
                id=uuid4(),
                title=result.title,
                hide_url=True,
                description=f"Price: {result.price:.2f}" + (f"   [{result.discount}]" if result.discount else  ""),
                thumb_url=f"https://cdn.akamai.steamstatic.com/steam/apps/{result.appid}/capsule_sm_120.jpg?t",  #low qual thumb
                # description=description,
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    message_text=f"[{result.title}]({result.link})\nPrice: R$ {result.price:.2f}" + (f"\nDiscount: -{discountToEmoji(result.discount)}%" if result.discount else ""), #https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg? can be used in order to not show the game's description
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

class SteamAsyncResults:
    def __init__(self, MAX_RESULTS):
        self.API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}"
        self.MAX_RESULTS = MAX_RESULTS
        self.API_GAME_SEARCH = "https://store.steampowered.com/search/suggest?term={}&f=games&cc=BR&realm=1&l=english"
    
    def getTasks(self, games: list, session: aiohttp.ClientSession):
        tasks = []
        for gamename in games:
            tasks.append((session.get(self.API_GAME_SEARCH.format(gamename))))
        return asyncio.gather(*tasks)

    async def getGames(self, games: list):
        async with aiohttp.ClientSession() as session:
            return await self.getTasks(games, session)

    async def processAsyncGames(self, games_input: list):
        responses = await self.getGames(games_input)
        appids = {}
        for response in responses:
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')
            for l in soup.find_all('a'):
                if l.has_attr("data-ds-appid"):
                    appids[l["data-ds-appid"]] = ""
        return appids

    async def getGameDetailsFromAppid(self, appid, session):
        async with session.get(API_APP_DETAILS_URL.format(appid)) as r:
            return await r.json()

    async def getAllGameDetails(self, appids, session):
        tasks =[asyncio.create_task(self.getGameDetailsFromAppid(appid, session)) for appid in appids]
        results = await asyncio.gather(*tasks)
        return results

    async def getGameResultsFromQuery(self, query:str):
        appidsAsync = (await self.processAsyncGames((query,)))
        responses = appidsAsync

        async with aiohttp.ClientSession() as session:
            data = tuple(GameResult.makeGameResultFromSteamApiGameDetails(gameDetail, {}) for gameDetail in (await self.getAllGameDetails(tuple(responses.keys()), session)))
            return data
        
    def getDetailsQuerySync(self, query):
        data = asyncio.run(self.getGameResultsFromQuery(query))
        return data
