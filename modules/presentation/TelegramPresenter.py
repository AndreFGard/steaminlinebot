from collections import defaultdict
from os import replace
from typing import Optional
from telegram import (
    InlineKeyboardMarkup,
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultsButton,
    InputTextMessageContent,
    InlineKeyboardButton,
)
from modules import ProtonDBReport
from modules.InlineQueryMaker import InlineQueryMaker
from uuid import uuid4
from modules.GameResult import GameResult
from dataclasses import dataclass

from modules.services import SearchGames
from modules.services.SearchGames import GameResultVM, ProtonDBVM, SearchResults, SpecialResults
from modules.services.UserCountry import CountryConfig, CountryModification

@dataclass
class TelegramPresentation:
    keyboard: InlineKeyboardMarkup
    text: str
    parse_mode: str

    def __post_init__(self):
        if self.parse_mode not in ["HTML", "Markdown"]:
            raise ValueError("parse_mode must be either 'HTML' or 'Markdown'")

@dataclass
class TelegramArticleInlineArticlePresentation(TelegramPresentation):
    queryArticle: Optional[InlineQueryResultArticle]

@dataclass
class TelegramCountryPresentation(TelegramPresentation):
    ...


class TelegramCallbackBuilder:
    @staticmethod
    def setcurrency(countrycode):
        return f"setcurrency {countrycode}"

class TelegramInlineQueryMaker:
    @staticmethod
    def _presentProtonDBVM(protondb: ProtonDBVM|None):
        if not protondb: return ''
        tierEmoji = protondb.tier.to_emoji()

        text = (
            f"[ProtonDB Tier](https://www.protondb.com/app/{protondb.appid}): {str(protondb.tier)}"
            f" {'📈' if protondb.positive_trend else '📉'}"
            f"{tierEmoji}"
            f"\t({protondb.totalReports} reports)"
        )
        return text
    @staticmethod
    def _gamePriceLine(game:GameResultVM):
        price = (
            "Price: FREE" if game.is_free else
            f"Price: {game.price}" if game.price is not None else
            "Not purchasable")
        return price
    @staticmethod
    def _presentGameResultVM(game: GameResultVM):
        price = TelegramInlineQueryMaker._gamePriceLine(game)
        discount = f"\t[{game.discount}]" if game.discount is not None else ''

        return (
            f"[{game.title}]({game.link})" + '\n' +
            price + discount + '\n' +
            TelegramInlineQueryMaker._presentProtonDBVM(game.protonDB)
        )

    @staticmethod
    def _makeInlineGameArticle(game: GameResultVM, countryConfig:CountryConfig):
        keyboardMarkup = TelegramInlineQueryMaker._makeKeyboardMarkup(
            appid=game.appid,
            steamlink=game.link,
            resultId=game.id,
            hasProtonDB=game.protonDB is not None
        )
        
        message_text = TelegramInlineQueryMaker._presentGameResultVM(game)


        #this must be refactored asap.
        # at this point it's soldered rather than coupled
        queryResult= InlineQueryResultArticle(
            id=str(uuid4()),
            title=game.title,
            description=TelegramInlineQueryMaker._gamePriceLine(game),
            thumbnail_url=(
                f"https://cdn.akamai.steamstatic.com/steam/apps/"
                f"{game.appid}/capsule_sm_120.jpg?t"
            ),
            input_message_content=InputTextMessageContent(
                parse_mode="Markdown",
                message_text=message_text,
            ),
            reply_markup=keyboardMarkup
        )

        return TelegramArticleInlineArticlePresentation(
            queryArticle = queryResult,
            text=message_text,
            keyboard=keyboardMarkup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    def _makeInlineQueryResultList(games:SearchResults):

    @staticmethod
    def _makeCountryKeyboard(codes:list[str]):
        keyboard = []
        for i in range(0, len(codes), 3):
            row = [
                InlineKeyboardButton(code, callback_data=TelegramCallbackBuilder.setcurrency(code))
                for code in codes[i:i+3]
            ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def makeCurrencyMessageFromCountry(countryMod: CountryModification):
        if countryMod.configuredCountry or countryMod.requestedCountry:
            if countryMod.configuredCountry:
                text =f"Your currency has been set to {countryMod.configuredCountry}✅"
                kb = InlineKeyboardMarkup([])
            else:
                text =(
                    f"Could not set currency to *{countryMod.requestedCountry}*. Is it a valid country code?"                
                    "\nPerhaps you meant one of those:"
                )
                kb = TelegramInlineQueryMaker._makeCountryKeyboard(countryMod.alternativeSuggestions)
        else:
            text = (
                "**How to set your currency:**\n"
                "Use `/setcurrency CODE` (e.g., `/setcurrency US`).\n\n"
                "Select one of the popular options below:"
            )
            kb = TelegramInlineQueryMaker._makeCountryKeyboard(countryMod.alternativeSuggestions)
            
        return TelegramCountryPresentation(text=text, keyboard=kb, parse_mode="Markdown")
    

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
        
        return InlineKeyboardMarkup(
            [list(row1conts.values()),list(row2conts.values())])
        
CHANGE_CURRENCY_BUTTON = InlineQueryResultsButton(
    text="Change currency / hide this", start_parameter="changecurrency")

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
