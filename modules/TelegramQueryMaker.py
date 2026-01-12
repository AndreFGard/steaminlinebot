from telegram import InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent,InlineKeyboardButton
from modules.InlineQueryMaker import InlineQueryMaker
from uuid import uuid4
from modules.GameResult import GameResult


class TelegramInlineQueryMaker(InlineQueryMaker):
    def __init__(self, *args,**kwargs):
        super().__init__(*args,**kwargs)

    @staticmethod
    def _digitsToEmoji(digit: str):
        emojis = ("0⃣", "1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣")
        answer = ""
        for d in digit:
            answer += emojis[int(d)]    
        return answer

    @staticmethod
    def _discountToEmoji(discount: str):
        return TelegramInlineQueryMaker._digitsToEmoji(discount[1:-1])

    @staticmethod
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
            raise Exception(f"Error in makeInlineQueryResultArticle: {e} (type: {type(e).__name__})")

ERROR_RESULT=InlineQueryResultArticle(id=str(uuid4()),
                title="Error",description=("Error: Sorry. Please report this with the /report command so we can fix it."),
                input_message_content=InputTextMessageContent(parse_mode="Markdown",
                message_text=("Error: Something has gone wrong here. Please report this with the /report command so I can fix it."),),)

TOO_SHORT_RESULT = InlineQueryResultArticle(
    id=str(uuid4()),
    title="Query Too Short",
    description="Please enter more characters to search.",
    input_message_content=InputTextMessageContent(
        parse_mode="Markdown",
        message_text="Your search query is too short. Please enter more characters."
    ),
)

NO_MATCHES_RESULT = InlineQueryResultArticle(
    id=str(uuid4()),
    title="No Matches Found",
    description="No games matched your search.",
    input_message_content=InputTextMessageContent(
        parse_mode="Markdown",
        message_text="No games matched your search. Try a different query."
    ),
)