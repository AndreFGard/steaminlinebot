from typing import Optional
import logging

from pydantic import BaseModel
from modules.services.Money import Money
from modules.services.ProtonDBClient import ProtonDBReport
from dataclasses import dataclass, field

class GameResult(BaseModel):
    link: str
    title: str
    appid: str
    price:Optional[Money]
    is_free: bool
    country: Optional[str]
    discount: Optional[int]
    protonDBReport: Optional[ProtonDBReport] = None
    
    def __repr__(self):
        return str({
                    'link': self.link,
                    'title': self.title,
                    'appid': self.appid,
                    'price': self.price,
                    'discount': self.discount,
                    'protonDBReport': self.protonDBReport
                })

