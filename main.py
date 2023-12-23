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

# def alternative(key:any, dict: dict, alternativeKey, alternativeDict={}: dict, fail=""):
#     if key in dict:
#         return dict[key]
#     elif alternativeKey != "" and alternativeKey in alternativeDict


itad_key = os.environ["ITAD_KEY"]
def inlinequery(update, context):
    req_start_T = time.time()
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
    souping_start_t = time.time()
    html = Soup(page)
    #filtering for data-ds-appids results in not showing bundles, requiring
    # appropriate filtering in the pricetags too, which is not implemented
    tags = html.find("a", {"data-ds-tagids": ""}, mode="all")
     # html tags containing info about each game
    # pricetags = html.find("div", {"class": "col search_price_discount_combined responsive_secondrow"}, mode="all")
    # i = 0
    # indexedPricetags = []
    # pricetagIndex = 0
    # for pricetag in pricetags:
    #     price = int(pricetag.attrs["data-price-final"]) * 0.01
    #     indexedPricetags.append(price)
    #     #print(f"ADD: {indexedPricetags[pricetagIndex]} and price {price} and pricetagindex {pricetagIndex}") #debug

    # gametagIndex=0
    tag_start_t = time.time()
    for tag,i in zip(tags, range(MAX_RESULTS)):
        #DBGprint(f"start{tag.text}")
        link = tag.attrs["href"]
        title = tag.text
        #if appid is not in there, it's a bundle.
        appid = tag.attrs["data-ds-appid"] if "data-ds-appid" in tag.attrs else tag.attrs["data-ds-bundleid"]
        itad_plain = cacheApp.storage[appid] if appid in cacheApp.storage else "not found"

        pricetag = tag.find("div", {"class": "col search_price_discount_combined responsive_secondrow"}, mode="first")
        price = int(pricetag.attrs["data-price-final"]) * 0.01
        discount = pricetag.text if pricetag.text.startswith("-") else ""

        #DBGprint(f"tile: {title}|\n")

        results.append(
            InlineQueryResultArticle(
                id=uuid4(),
                title=title,
                hide_url=True,
                description=f"Price: {price:.2f}" + (f"   [{discount}]" if discount else  ""),
                thumb_url=f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/capsule_sm_120.jpg?t",  #low qual thumb
                # description=description,
                input_message_content=InputTextMessageContent(
                    parse_mode="Markdown",
                    message_text=f"[{title}]({link})\nPrice: R$ {price:.2f}" + (f"\nDiscount: -{modules.discountToEmoji(discount)}%" if discount else ""), #https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg? can be used in order to not show the game's description
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
    tag_end = time.time()

    #DBGprint("OVER")
    try: 
        update.inline_query.answer(results, cache_time=30)
        update_end = time.time()    
        tag_time_total = tag_end - tag_start_t 
        tagt_avg = tag_time_total / MAX_RESULTS
        req_t =  souping_start_t - req_start_T 
        print(f"answer building total time: {req_t + tag_time_total}:")
        print(f"\tpage download Time: {req_t}")
        print(f"\tpage souping/scraping time: {tag_start_t - souping_start_t}")
        print(f"\ttag building time: {tag_time_total}| per tag= {tagt_avg}")
        print(f"uploading time: {-tag_end +   update_end}. TOTAL: {update_end - tag_end + req_t + tag_time_total}")
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
