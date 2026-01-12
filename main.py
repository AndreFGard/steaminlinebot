#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Telegram bot for searching through Steam and protondb pages
# This program is dedicated to the public domain under the GPL3 license.

"""
Inspired by the archewikibot
"""
"""
@Steaminlinebot written by GuaximFsg (now AndreFGard) on github
"""

from math import trunc
import os
import sys
import logging
from uuid import uuid4
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Updater, InlineQueryHandler, CommandHandler
from telegram import InlineQueryResultArticle, InputTextMessageContent
import json
import modules
import time

MAX_RESULTS = 6
import dotenv
dotenv.load_dotenv()

itad_key = ''


ERROR_RESULT = modules.ERROR_RESULT 

# Enable logging
# logging.basicConfig(
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     level=logging.INFO,
# )

# logger = logging.getLogger(__name__)


async def start(update: Update, context):
    return await update.message.reply_text( #type:ignore
        "This bot can search for steam games for you in in-line mode.\n/help for more info.",
    )


async def help(update: Update, context):
    return await update.message.reply_text( #type:ignore
        "To search with this bot, type @Steaminlinebot and then something " 
        "you want to search in the message box. for example:\n"
        "@Steaminlinebot Skyrim\n"
        "or\n"
        "@steaminlinebot Stardew Valley",
    )




steamSearcher = modules.SteamSearcher(MAX_RESULTS)
async def inlinequerySteamApi(update: Update, context):
    start = time.time()
    query = update.inline_query.query #type:ignore
    if len(query) < 3:
        return
    
    try:
        gameResults = await steamSearcher.makeGameResultsFromGameDetails(query)
        if len(gameResults) == 0:
            gameResults = [ERROR_RESULT]
    except:
        gameResults = [ERROR_RESULT]


    telegramResultArticles =  list(map(modules.makeInlineQueryResultArticle, gameResults))
    for idx,game in enumerate(telegramResultArticles):
        if not game:
            #move errored result to the end of the list
            telegramResultArticles.pop(idx)
            telegramResultArticles.append(modules.ERROR_RESULT)
    results = list(filter(lambda x: isinstance(x, InlineQueryResultArticle), telegramResultArticles))
    start_uploading = time.time()
    await update.inline_query.answer(results, cache_time=30)
    end = time.time()
    print(f"took {(start_uploading - start):.4f}s + {(end - start_uploading):.4f}s")

#choose which version to use here
INLINEQUERYFUNC = inlinequerySteamApi

def error(update, context):
    print(f"Update {update} caused error {context.error}")


def main():
    # Create the Updater and pass it your bot's token.
    try:
        token = os.environ["BOT_TOKEN"]
    except KeyError:
        print("No BOT_TOKEN environment variable passed. Terminating.")
        sys.exit(1)
    
    from telegram.ext import Application
    
    # Create the Application
    application = Application.builder().token(token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))

    # on noncommand i.e message - echo the message on Telegram
    application.add_handler(InlineQueryHandler(INLINEQUERYFUNC))

    # log all errors
    application.add_error_handler(error)

    # Start the Bot
    application.run_polling()


if __name__ == "__main__":
    main()
