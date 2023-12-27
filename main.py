#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Telegram bot for searching through Steam and protondb pages
# This program is dedicated to the public domain under the GPL3 license.

"""
Original archewiki bot Written by: @Alireza6677
                                   alireza6677@gmail.com

original archewikibot Updated in 27/05/2021 by: @NicKoehler
"""
"""
@Steaminlinebot written by GuaximFsg on github
"""

from math import trunc
import os
import sys
import requests
import logging
from uuid import uuid4
from gazpacho import get, Soup
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent
import json
import modules
import time

MAX_RESULTS = 6
try:
    cacheApp = modules.cachev0("dict-steamappid-itadplain.json")
    """Contains a map between steam appids and is there any deal yet plains"""
except:
    print("CACHE FILE NOT FOUND")
    cacheApp = modules.cachev0("")

ERROR_RESULT = InlineQueryResultArticle(
                id=uuid4(),
                title="Error",
                hide_url=True,
                description=("Error: Sorry. Please report this with the /report command so we can fix it."),
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    message_text=("Error: Sorry. Please report this with the /report command so we can fix it."),),)

# Enable logging
# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     level=logging.INFO,
# )

# logger = logging.getLogger(__name__)

class logger:
    def critica(a):
        print(a)
    def error (a):
        print(a)
    def warning(a):
        print(a)

def start(update, context):
    update.message.reply_text(
        "This bot can search for steam games for you in in-line mode.\n/help for more info.",
    )


def help(update, context):
    update.message.reply_text(
        """To search with this bot you can easily type @Steaminlinebot and then something you want to search. for example :
@Steaminlinebot Skyrim
or
@steaminlinebot Stardew Valley
...""",
    )


itad_key = os.environ["ITAD_KEY"]
def inlinequery(update, context):
    query = update.inline_query.query

    telegramResults = modules.scrapSteam(query, MAX_RESULTS, cacheApp)
    results = [result for result in telegramResults if result]
    if len(results) == 0:
        results = [ERROR_RESULT]
    #DBGprint("OVER")
    try: 
        update.inline_query.answer(results, cache_time=30)

    except:
        print("poping")
        results.pop(-1)
        update.inline_query.answer(results, cache_time=30)



def error(update, context):
    logger.warning(f"Update {update} caused error {context.error}")


def main():
    # Create the Updater and pass it your bot's token.
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        logger.critical("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)
    updater = Updater(token)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(InlineQueryHandler(inlinequery))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Block until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == "__main__":
    main()
