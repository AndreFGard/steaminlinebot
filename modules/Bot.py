from sqlite3 import Connection
from modules.GameResult import GameResult
from modules.TelegramQueryMaker import (
    CHANGE_CURRENCY_BUTTON,
    TelegramInlineQueryMaker,
    ERROR_RESULT,
    TOO_SHORT_RESULT,
    NO_MATCHES_RESULT,
)
from modules.SteamSearcher import SteamSearcher

import logging
import time

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent

from modules.db.UserRepository import UserRepository



class Bot:
    def __init__(self, db:Connection):
        self.queryMaker = TelegramInlineQueryMaker(SteamSearcher(MAX_RESULTS=6))
        self.db = db
        self.userRepo = UserRepository(db)

    def _get_country(self, id, fallback_languages=[]):
        country = self.userRepo.get_user_country(id)
        has_set=True
        if not country:
            has_set = False
            for l in fallback_languages:
                country = self.userRepo.get_country(l)
                if country: break

        if not country: country = "US"
        return (has_set,country )

    async def handleInlineQuery(self, update: Update, context):
        query = update.inline_query.query  # type:ignore
        logging.warning(update)
        start = time.time()

        specialResults = set()
        results = []
        gameResults = []
        hasSetCountry = None

        if len(query) < 3:
            specialResults.add(TOO_SHORT_RESULT)
        else:
            try:
                hasSetCountry,country = self._get_country(
                    update.inline_query.from_user.id,#type:ignore
                    fallback_languages=[update.inline_query.from_user.language_code, "en-us"]) #type:ignore

                res = await self.queryMaker.scrapeQuery(query, country)
                gameResults = res.results

                if not gameResults:
                    specialResults.add(NO_MATCHES_RESULT)

                if res.found_error:
                    specialResults.add(ERROR_RESULT)  # type:ignore

                # telegram Inline Objects that are actually rendered after they are tap sent
                results: list[InlineQueryResultArticle] = []
                for r in gameResults:
                    try:
                        results.append(self.queryMaker.makeInlineQueryResultArticle(r))
                    except Exception as e:
                        print(f"LOG: ERROR: {e}")
                        specialResults.add(ERROR_RESULT)

            except Exception as e:
                print(f"LOG: Failed to query: {e}")
                specialResults.add(ERROR_RESULT)  # type:ignore

        updateTime = time.time()

        ##                                    <--------------------- magic here
        await update.inline_query.answer( #type:ignore
            results + list(specialResults),
            cache_time=30,
            button=CHANGE_CURRENCY_BUTTON if hasSetCountry == False else None
        )

        endTime = time.time()
        logging.info(f"RESULTS : {gameResults}")
        print(
            f"LOG: scrape time: {(updateTime - start):.4f}s, totalTime: {(endTime - start):.4f}s"
        )

    async def update_currency(self, update:Update):
        id = update.effective_sender.id #type:ignore
        update.message