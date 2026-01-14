from typing import Optional
import logging

from modules.ProtonDB import ProtonDBReport
from dataclasses import dataclass, field

@dataclass
class GameResult:
    link: str
    title: str
    appid: str
    price: float
    discount: Optional[str]
    protonDBReport: Optional[ProtonDBReport] = None

    @staticmethod
    def makeGameResultFromSteamApiGameDetails(gamedetails:dict, protonDBReport:Optional[ProtonDBReport] = None):
        try:
            appid: str = tuple(gamedetails.keys())[0]

            if gamedetails[appid]['success']:
                data = gamedetails[appid]['data']
                title = data['name']
                link = f"https://store.steampowered.com/app/{appid}/"
                price = 0.0
                if data['is_free'] or 'price_overview' not in data:
                    price = 0.0
                    discount = None
                else:
                    price = data['price_overview']['final_formatted']
                    if price == 0.0:
                        discount = None
                    else:
                        discountAmount = float(str(data['price_overview']['discount_percent']))
                        discount = f"-{discountAmount:.2f}%" if discountAmount > 0 else None

                return(GameResult(link=link, title=title, appid=appid, price=price, discount=discount, protonDBReport=protonDBReport))
        except Exception as e:
            logging.info(f"Error in makeGameResultFromSteamApiGameDetails: {e}")
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

