from collections import defaultdict
from os import replace
from telegram import (
    InlineKeyboardMarkup,
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    InlineKeyboardButton,
)
from modules.InlineQueryMaker import InlineQueryMaker
from uuid import uuid4
from modules.GameResult import GameResult
from dataclasses import dataclass

@dataclass
class TelegramVM:
    keyboard: InlineKeyboardMarkup
    text: str
    parse_mode: str

    def __post_init__(self):
        if self.parse_mode not in ["HTML", "Markdown"]:
            raise ValueError("parse_mode must be either 'HTML' or 'Markdown'")


class TelegramInlineQueryMaker:

    @staticmethod
    def _digitsToEmoji(digit: str):
        emojis = ("0⃣", "1⃣", "2⃣", "3⃣", "4⃣", "5⃣", "6⃣", "7⃣", "8⃣", "9⃣")
        answer = ""
        for d in digit:
            answer += emojis[int(d)]
        return answer

    @staticmethod
    def _discountToEmoji(discount: str):
        return TelegramInlineQueryMaker._digitsToEmoji(discount[1:-1])

    @staticmethod
    def makeInlineQueryResultArticle_interactive(result: GameResult, resultId:int):
        try:

            if result.is_free:
                price_text = "Price: FREE"
            elif result.price is not None:
                price_text =f"Price: {result.price}"
            else:
                #possibly to be announced or just not sellable
                price_text = ""

            if result.discount:
                price_text += f"\t[{result.discount}]"

            message_text = (
                f"[{result.title}]({result.link})\n"
                + price_text + '\n'
            )

            if result.protonDBReport is not None:
                tier = result.protonDBReport.tier
                is_positive_trend = result.protonDBReport.trendingTier > result.protonDBReport.tier
                trend_text = f"{tier.label()}📈" if is_positive_trend else f"{tier.label()}📉"

                message_text += (
                    f"\nProtonDB Tier: *{tier.label()}*"
                    f"{tier.to_emoji()}"
                    f"\nTrending: {trend_text}"
                )

            keyboardMarkup = TelegramInlineQueryMaker._makeKeyboardMarkup(
                appid=result.appid,
                steamlink=result.link,
                resultId=resultId,
                hasProtonDB=result.protonDBReport is not None
            )
                        
            #this must be refactored asap.
            # at this point it's soldered rather than coupled
            return InlineQueryResultArticle(
                id=str(uuid4()),
                title=result.title,
                description=price_text,
                thumbnail_url=(
                    f"https://cdn.akamai.steamstatic.com/steam/apps/"
                    f"{result.appid}/capsule_sm_120.jpg?t"
                ),
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    message_text=message_text,
                ),
                reply_markup=keyboardMarkup
            ),message_text, keyboardMarkup

        except Exception as e:
            raise Exception(
                f"Error in makeInlineQueryResultArticle: {e} "
                f"(type: {type(e).__name__})"
            )
    @staticmethod
    def makeProtonDBResultText(result: GameResult, resultId:int):
        try:
            message_text = ""
            if result.protonDBReport is not None:
                tier = result.protonDBReport.tier
                is_positive_trend = result.protonDBReport.trendingTier > result.protonDBReport.tier
                trend_text = f"{tier.label()}📈" if is_positive_trend else f"{tier.label()}📉"
                message_text += (
                    f"\n[ProtonDB](https://www.protondb.com/app/{result.appid}) Tier: *{tier.label()}*"
                    f"{tier.to_emoji()}\t({result.protonDBReport.total} reports)"
                    f"\nTrending: {trend_text}"
                )

                keyboardMarkup = TelegramInlineQueryMaker._makeKeyboardMarkup(
                    appid=result.appid,
                    steamlink=result.link,
                    resultId=resultId,
                    hasProtonDB=True,
                    replace_back="PROTONDB"
                )
                return message_text,keyboardMarkup
            else:
                return f"[ProtonDB](https://www.protondb.com/app/{result.appid}) info couldnt be fetched", InlineKeyboardMarkup([])
        except Exception as e:
            raise Exception(
                f"Error in makeProtonDBResultText: {e} "
                f"(type: {type(e).__name__})"
            )
    @staticmethod
    def _makeKeyboardMarkup(appid, steamlink, resultId:int, hasProtonDB:bool, replace_back=None):
        row1conts = {
            "STEAM": InlineKeyboardButton("Steam Page", url=steamlink),
            "PROTONDB": InlineKeyboardButton(
                "ProtonDB 🐧",
                #url=f"https://www.protondb.com/app/{result.appid}",
                callback_data=f"protondb_cb {resultId}" #will call _handle_game_result_callback
                )
        }
        row2conts = {"PRICEHISTORY": InlineKeyboardButton(
            "Price History",url=(f"https://steamdb.info/app/{appid}/#pricehistory"))}
        backButton = InlineKeyboardButton("Overview", callback_data=f"overview_cb {resultId}")
        
        replaceable: None|dict = None
        if replace_back in row1conts:
            replaceable = row1conts
        elif replace_back in row2conts:
            replaceable = row2conts
        
        if replaceable is not None:
            replaceable[replace_back] = backButton
        
        if replaceable != row1conts and  not hasProtonDB:
            row1conts.pop("PROTONDB")
        
        return InlineKeyboardMarkup([list(row1conts.values()), list(row2conts.values())])
        
        
                

    
CHANGE_CURRENCY_BUTTON = InlineQueryResultsButton(text="Change currency / hide this", start_parameter="changecurrency")

ERROR_RESULT = InlineQueryResultArticle(
    id=str(uuid4()),
    title="Error",
    description=(
        "Error: Sorry. Please report this with the /report command so we can fix it."
    ),
    input_message_content=InputTextMessageContent(
        parse_mode="Markdown",
        message_text=(
            "Error: Something has gone wrong here. Please report this with the /report command so I can fix it."
        ),
    ),
)

TOO_SHORT_RESULT = InlineQueryResultArticle(
    id=str(uuid4()),
    title="Query Too Short",
    description="Please enter more characters to search.",
    input_message_content=InputTextMessageContent(
        parse_mode="Markdown",
        message_text="Your search query is too short. Please enter more characters.",
    ),
)

NO_MATCHES_RESULT = InlineQueryResultArticle(
    id=str(uuid4()),
    title="No Matches Found",
    description="No games matched your search.",
    input_message_content=InputTextMessageContent(
        parse_mode="Markdown",
        message_text="No games matched your search. Try a different query.",
    ),
)
