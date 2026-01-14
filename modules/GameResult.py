from typing import Optional

from modules.ProtonDB import ProtonDBReport

class GameResult:
    def __init__(self, link:str, title:str, appid:str,itad_plain:str,price:float,discount:Optional[str], cacheStorage: dict = {}, price_formatted :int = False, protonDBReport: Optional[ProtonDBReport]=None):
        self.link = link
        self.link = link
        self.title = title
        self.appid = appid
        self.itad_plain = itad_plain
        self.discount = discount
        self.price = price
        self.protonDBReport = protonDBReport

    @staticmethod
    def makeGameResultFromSteamApiGameDetails( gamedetails:dict,cacheStorage: dict ={}, protonDBReport:Optional[ProtonDBReport] = None):
        try:
            appid: str = tuple(gamedetails.keys())[0]
            if gamedetails[appid]['success']:
                data = gamedetails[appid]['data']
                title = data['name']
                link = f"https://store.steampowered.com/app/{appid}/"
                itad_plain = cacheStorage[appid] if appid in cacheStorage else "not found"
                price = 0.0
                if data['is_free'] or 'price_overview' not in data:
                    price = 0.0
                    discount = None
                else:
                    price = data['price_overview']['final_formatted']
                    discountAmount = float(str(data['price_overview']['discount_percent']))
                    discount = f"-{discountAmount:.2f}%" if discountAmount > 0 else ''
                print(f"{title}: {price} - {appid}")
                return(GameResult(link, title, appid, itad_plain, price, discount, cacheStorage, protonDBReport=protonDBReport))
        except Exception as e:
            print(f"Error in makeGameResultFromSteamApiGameDetails: {e}")
            return None
        
    def __repr__(self):
        return str({
                    'link': self.link,
                    'title': self.title,
                    'appid': self.appid,
                    'itad_plain': self.itad_plain,
                    'price': self.price,
                    'discount': self.discount,
                    'protonDBReport': self.protonDBReport
                })

