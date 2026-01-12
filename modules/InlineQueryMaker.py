from telegram import InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent,InlineKeyboardButton
from modules.SteamSearcher import SteamSearcher
class InlineQueryMaker:
    def __init__(self, scraper: SteamSearcher):
        self.scraper = scraper


    async def scrapeQuery(self, query ):
        return await self.scraper.scrapeGameResults(query)

        
