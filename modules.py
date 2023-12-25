import json
import gazpacho
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from uuid import uuid4

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
    def __init__(self, tag: list, cacheStorage):
        self.link = tag.attrs["href"]
        self.title = tag.text
        #if appid is not in there, it's a bundle.
        self.appid = tag.attrs["data-ds-appid"] if "data-ds-appid" in tag.attrs else tag.attrs["data-ds-bundleid"]
        self.itad_plain = cacheStorage[self.appid] if self.appid in cacheStorage else "not found"

        self.pricetag = tag.find("div", {"class": "col search_price_discount_combined responsive_secondrow"}, mode="first")
        self.price = int(self.pricetag.attrs["data-price-final"]) * 0.01
        self.discount = self.pricetag.text if self.pricetag.text.startswith("-") else ""

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