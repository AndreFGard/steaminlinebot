from typing import Optional
import logging

from modules.ProtonDB import ProtonDBReport
from dataclasses import dataclass, field

@dataclass
class GameResult:
    link: str
    title: str
    appid: str
    price: str
    discount: Optional[str]
    protonDBReport: Optional[ProtonDBReport] = None


    @staticmethod
    def makeGameResultFromSteamApiGameDetails(gamedetails:dict, protonDBReport:Optional[ProtonDBReport] = None):
        try:
            appid: str = tuple(gamedetails.keys())[0]

            if not gamedetails[appid]['success']:
                raise Exception(f"Unsuccessful gamedetails result: {gamedetails}")

            link = f"https://store.steampowered.com/app/{appid}/"
            data = gamedetails[appid]['data']
            title = data['name']
            
            discount = None
            if data['is_free'] or 'price_overview' not in data:
                price = None
                discount = None
            else:
                price = str(data['price_overview']['final_formatted'])
                try: 
                    if float(price.split()[1].replace(",",".")) == 0.0:
                        price = None
                        discount = None
                    else:
                        discountAmount = float(str(data['price_overview']['discount_percent']))
                        discount = f"-{discountAmount:.0f}%" if discountAmount > 0 else None
                except Exception as e:
                    logging.warning(f"Price parsing error: {e}")

            return(GameResult(link=link, title=title, appid=appid, price=price, discount=discount, protonDBReport=protonDBReport))

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

