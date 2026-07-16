from typing import Optional

import pydantic
from modules.services.Money import Money
from modules.services.ProtonDBClient import ProtonDBReport


class GameResult(pydantic.BaseModel):
    link: str
    title: str
    appid: str
    price: Optional[Money]
    is_free: bool
    country: Optional[str]
    discount: Optional[int]
    proton_db_report: Optional[ProtonDBReport] = None

    def __repr__(self):
        return str(
            {
                "link": self.link,
                "title": self.title,
                "appid": self.appid,
                "price": self.price,
                "discount": self.discount,
                "proton_db_report": self.proton_db_report,
            }
        )
