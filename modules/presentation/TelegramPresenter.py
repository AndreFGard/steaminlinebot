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
class TelegramInlineArticlePres(TelegramPresentation):
    queryArticle: InlineQueryResultArticle

@dataclass
class TelegramCountryPres(TelegramPresentation):
    ...

@dataclass
class TelegramInlineResultListPres:
    results: list[InlineQueryResultArticle]
    button: Optional[InlineQueryResultsButton]


class TelegramCallbackBuilder:
    @staticmethod
    def setcurrency(countrycode):
        return f"setcurrency {countrycode}"

class TelegramPresenter:
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
        price = TelegramPresenter._gamePriceLine(game)
        discount = f"\t[{game.discount}]" if game.discount is not None else ''

        return (
            f"[{game.title}]({game.link})" + '\n' +
            price + discount + '\n' +
            TelegramPresenter._presentProtonDBVM(game.protonDB)
        )

    @staticmethod
    def _makeInlineGameArticle(game: GameResultVM, countryConfig:CountryConfig):
        keyboardMarkup = TelegramPresenter._makeKeyboardMarkup(
            appid=game.appid,
            steamlink=game.link,
            hasProtonDB=game.protonDB is not None
        )
        
        message_text = TelegramPresenter._presentGameResultVM(game)


        #this must be refactored asap.
        # at this point it's soldered rather than coupled
        queryResult= InlineQueryResultArticle(
            id=str(uuid4()),
            title=game.title,
            description=TelegramPresenter._gamePriceLine(game),
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

        return TelegramInlineArticlePres(
            queryArticle = queryResult,
            text=message_text,
            keyboard=keyboardMarkup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    def _makeSpecialInlineQueryResult(result: SpecialResults)->InlineQueryResultArticle:
        match result:
            case SpecialResults.ERROR:
                return ERROR_RESULT
            case SpecialResults.QUERY_TOO_SHORT:
                return TOO_SHORT_RESULT
            case SpecialResults.NO_MATCHES:
                return NO_MATCHES_RESULT

    @staticmethod
    def _makeInlineQueryResultsList(games:SearchResults, countryConfig:CountryConfig):
        articles = [
            TelegramPresenter._makeInlineGameArticle(
                game,
                countryConfig
            ).queryArticle
            for game in games.results]
        articles.extend(
            TelegramPresenter._makeSpecialInlineQueryResult(r)
            for r in games.specialResults
        )
        button = None if not games.configureCountry else CHANGE_CURRENCY_BUTTON
        return TelegramInlineResultListPres(
            button=button,
            results=articles,

        )

    @staticmethod
    def makeInlineQueryPresentation(searchResults: SearchResults, countryConfig: CountryConfig) -> TelegramInlineResultListPres:
        return TelegramPresenter._makeInlineQueryResultsList(searchResults, countryConfig)

    @staticmethod
    def makeDeleteConfirmation(success: bool) -> TelegramPresentation:
        if success:
            text = "Your data has been deleted 🫡"
        else:
            text = "Failed to delete your data. Please report with /report"
        
        return TelegramPresentation(
            text=text,
            keyboard=InlineKeyboardMarkup([]),
            parse_mode="Markdown"
        )
        
    @staticmethod
    def _makeCountryKeyboard(codes:list[str]):
        keyboard = []
        for i in range(0, len(codes), 3):
            row = [
                InlineKeyboardButton(code, callback_data=TelegramCallbackBuilder.setcurrency(code))
                for code in codes[i:i+3]
            ]
            keyboard.append(row)
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
                kb = TelegramPresenter._makeCountryKeyboard(countryMod.alternativeSuggestions)
        else:
            text = (
                "**How to set your currency:**\n"
                "Use `/setcurrency CODE` (e.g., `/setcurrency US`).\n\n"
                "Select one of the popular options below:"
            )
            kb = TelegramPresenter._makeCountryKeyboard(countryMod.alternativeSuggestions)
            
        return TelegramCountryPres(text=text, keyboard=kb, parse_mode="Markdown")
    

    @staticmethod
    def _makeKeyboardMarkup(appid, steamlink, hasProtonDB:bool):
        row1buttons = [
            InlineKeyboardButton("Steam Page", url=steamlink)
        ]
        
        if hasProtonDB:
            row1buttons.append(
                InlineKeyboardButton(
                    "ProtonDB 🐧",
                    url=f"https://www.protondb.com/app/{appid}"
                )
            )
        
        row2buttons = [
            InlineKeyboardButton(
                "Price History",
                url=f"https://steamdb.info/app/{appid}/#pricehistory"
            )
        ]
        
        return InlineKeyboardMarkup([row1buttons, row2buttons])
        
CHANGE_CURRENCY_BUTTON = InlineQueryResultsButton(
    text="Change currency / hide this", start_parameter="/setcurrency")

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
