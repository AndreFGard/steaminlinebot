import json
import gazpacho
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import uuid4
from bs4 import BeautifulSoup
import aiohttp
import asyncio

API_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails?filters=basic,price_overview&appids={}"



class cachev0:
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
        
#results = list(map(makeInlineQueryResultArticle))