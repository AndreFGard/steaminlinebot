from babel.numbers import format_currency, get_currency_precision
from babel import Locale
from decimal import Decimal
from dataclasses import dataclass
import logging
from typing import Optional
from datetime import date


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
