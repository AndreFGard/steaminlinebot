from decimal import Decimal
from dataclasses import dataclass

from babel.numbers import format_currency, get_currency_precision


@dataclass
class Money:
    country: str
    currency3l: str
    value_minor: int

    def present(self):
        format = format_currency(
            self.value_minor / Decimal(10 ** get_currency_precision(self.currency3l)),
            self.currency3l,
        )
        return format
