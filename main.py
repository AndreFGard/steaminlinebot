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

tag = 0

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
    results = []

    prefix = "https://store.steampowered.com/search/?term="
    if len(query) < 3:
        return
    query = query.replace(' ', '+') #necessary for queries with spaces to work
    try:
        page = get(prefix + query + "&cc=BR") #&cc=BR makes the search use Brazilian regional pricing
    except Exception as e:
        update.message.reply_text("Sorry, Steam is offline.")
        logger.error(e)
        return

    html = Soup(page)
    tags = html.find(
        "a", {"data-ds-appid": ""}, mode="all"
    )  # html tags containing info about each game
    pricetags = html.find(
        "div",
        {"class": "col search_price_discount_combined responsive_secondrow"},
        mode="all",
    )
    i = 0
    indexedPricetags = []
    pricetagIndex = 0
    for pricetag in pricetags:
        price = int(pricetag.attrs["data-price-final"]) * 0.01
        indexedPricetags.append(price)
        #print(f"ADD: {indexedPricetags[pricetagIndex]} and price {price} and pricetagindex {pricetagIndex}") #debug
        pricetagIndex += 1

    gametagIndex=0

    for tag in tags:
        if gametagIndex > 5: #limiting to five results for speed. not sure if there is actually any speed improvement
            break
        i +=1
        link = tag.attrs["href"]
        title = tag.text
        price = indexedPricetags[gametagIndex]
        gametagIndex += 1
        appid = tag.attrs["data-ds-appid"]
        #print(f"This is title: {title}\nAnd this is link: {link} and this is appid {appid} and this is PRICE: {price}") #debug

        #DBGprint("\n starting")
        itad_response = requests.get(f"https://api.isthereanydeal.com/v02/game/plain/?key={itad_key}&shop=steam&game_id=app%2F{appid}").content
        #DBGprint("itad_response: +" +str(itad_response))
        itad_response_j = json.loads(itad_response)
        #DBGprint("itad json: " + str(itad_response_j))
        try:
            itad_plain = itad_response_j["data"]["plain"] if itad_response_j[".meta"]["match"] else ""
        except:
            itad_plain = ""
        #DBGprint("itadplaim" + itad_plain)
        results.append(
            InlineQueryResultArticle(
                id=uuid4(),
                title=title,
                hide_url=True,
                description=f"Price: {price:.2f}",
                thumb_url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_sm_120.jpg?t",  #low qual thumb
                # description=description,
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    message_text=f"[{title}]({link})\nPrice: R$ {price:.2f}", #https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg? can be used in order to not show the game's description
                ),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Steam Page", url=link),
                            InlineKeyboardButton("ProtonDB 🐧",url=f"https://www.protondb.com/app/{appid}"),

                        
                        ],
                        [InlineKeyboardButton("Historico de preços", url=f"https://isthereanydeal.com/game/{itad_plain}/info/")], #creates a button in its own line, bellow the buttons above
                    ]
                ),
            )
        )
    
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
