#!/usr/bin/env python3
# This program is dedicated to the public domain under the GPL3 license.

"""
@Steaminlinebot written by GuaximFsg (now AndreFGard) on github
"""

from functools import cache
import os
import sys
from logging import basicConfig, WARNING, INFO, DEBUG
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent

import time
from telegram.ext import Application

from modules.GameResult import GameResult
from modules.TelegramQueryMaker import (
    TelegramInlineQueryMaker,
    ERROR_RESULT,
    TOO_SHORT_RESULT,
    NO_MATCHES_RESULT,
)
from modules.SteamSearcher import SteamSearcher

import dotenv

dotenv.load_dotenv()
logLevel = {""}

basicConfig(
    level={"WARNING": WARNING, "INFO": INFO, "DEBUG": DEBUG, None: WARNING}[
        os.environ.get("LOG_LEVEL")
    ],
    format="[%(levelname)s] %(asctime)s  %(name)s: %(message)s",
)


async def start(update: Update, context):
    return await update.message.reply_text(  # type:ignore
        "This bot can search for steam games for you in in-line mode.\n/help for more info.",
    )


async def help(update: Update, context):
    return await update.message.reply_text(  # type:ignore
        "To search with this bot, type @Steaminlinebot and then something "
        "you want to search in the message box. for example:\n"
        "@Steaminlinebot Skyrim\n"
        "or\n"
        "@steaminlinebot Stardew Valley",
    )


class Bot:
    def __init__(self):
        self.queryMaker = TelegramInlineQueryMaker(SteamSearcher(MAX_RESULTS=6))

    @staticmethod
    def sortGameResults(a):
        errors = [ERROR_RESULT, TOO_SHORT_RESULT, NO_MATCHES_RESULT]
        return list(filter(lambda x: x not in errors, a)) + list(
            filter(lambda x: x in a, errors)
        )

    async def handleInlineQuery(self, update: Update, context):
        query = update.inline_query.query  # type:ignore
        logging.warning(update)
        start = time.time()

        specialResults = set()
        results = []
        gameResults = []
        if len(query) < 3:
            specialResults.add(TOO_SHORT_RESULT)
        else:
            try:
                res = await self.queryMaker.scrapeQuery(query)
                gameResults = res.results

                if not gameResults:
                    specialResults.add(NO_MATCHES_RESULT)

                if res.found_error:
                    specialResults.add(ERROR_RESULT)  # type:ignore

                # telegram Inline Objects that are actually rendered
                results: list[InlineQueryResultArticle] = []
                for r in gameResults:
                    try:
                        results.append(self.queryMaker.makeInlineQueryResultArticle(r))
                    except Exception as e:
                        print(f"LOG: ERROR: {e}")
                        specialResults.add(ERROR_RESULT)

            except Exception as e:
                print(f"LOG: Failed to query: {e}")
                results.add(ERROR_RESULT)  # type:ignore

        updateTime = time.time()
        await update.inline_query.answer( #type:ignore
            results + list(specialResults), cache_time=30
        )
        endTime = time.time()
        logging.warning(f"RESULTS : {gameResults}")
        print(
            f"LOG: scrape time: {(updateTime - start):.4f}s, totalTime: {(endTime - start):.4f}s"
        )


def error(update: Update, context):
    print(f"Update {update} caused error {context.error}")


def main():
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        print("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)

    bot = Bot()

    # Create the Application
    application = Application.builder().token(token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    application.add_handler(InlineQueryHandler(bot.handleInlineQuery))

    # log all errors
    application.add_error_handler(error)  # type:ignore

    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()
