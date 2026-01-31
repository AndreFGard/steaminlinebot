from typing import Optional
import logging

from pydantic import BaseModel

from modules.services.ProtonDBClient import ProtonDBReport
from dataclasses import dataclass, field

class GameResult(BaseModel):
    link: str
    title: str
    appid: str
    price: Optional[str]
    is_free: bool
    country: Optional[str]
    discount: Optional[str]
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

