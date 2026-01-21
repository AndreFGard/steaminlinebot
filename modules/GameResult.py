from typing import Optional
import logging

from modules.ProtonDB import ProtonDBReport
from dataclasses import dataclass, field

@dataclass
class GameResult:
    link: str
    title: str
    appid: str
    price: Optional[str]
    is_free: bool
    discount: Optional[str]
    protonDBReport: Optional[ProtonDBReport] = None
    
    @staticmethod
    def _parseDiscount(priceStr, discountValue: int):
        """Parses discounts in different locales"""
        e = Exception()
        for valueidx in [0,1]:
            try: 
                if float(priceStr.split()[valueidx].replace(",",".")) == 0.0:
                    return None
                else:
                    if float(discountValue) == 0.0:
                        return None
                    discount = f"-{discountValue:.0f}%"
                    return discount
            except Exception as ee:
                e = ee
        logging.warning(f"Price parsing of price/discount: ('{priceStr}','{discountValue}') error: {e}")
        return None

    @staticmethod
    def makeGameResultFromSteamApiGameDetails(gamedetails:dict, protonDBReport:Optional[ProtonDBReport] = None):
        try:
            appid: str = tuple(gamedetails.keys())[0]

            if not gamedetails[appid]['success']:
                raise Exception(f"Unsuccessful gamedetails result: {gamedetails}")

            link = f"https://store.steampowered.com/app/{appid}/"
            data = gamedetails[appid]['data']
            title = data['name']
            
            has_price = False
            is_free = False
            discount = None

            if data['is_free']:
                is_free = True
                price = None
            elif 'price_overview' not in data:
                price = None
                discount = None
            else:
                #This is a WIP, as the value position changes based on locales/countries
                price = str(data['price_overview']['final_formatted'])
                discount = GameResult._parseDiscount(price, data["price_overview"]["discount_percent"])

            return(GameResult(link=link, title=title, appid=appid, price=price, discount=discount, protonDBReport=protonDBReport, is_free=is_free))

        except Exception as e:
            logging.warning(f"Error in makeGameResultFromSteamApiGameDetails: {e}")
            return None
        

    def __repr__(self):
        return str({
                    'link': self.link,
                    'title': self.title,
                    'appid': self.appid,
                    'price': self.price,
                    'discount': self.discount,
                    'protonDBReport': self.protonDBReport
                })

