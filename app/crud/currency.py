from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.currency import Currency


class CurrencyCrud:
    def __init__(self, db: Session):
        self.db = db

    def get(self, code: str) -> Optional[Currency]:
        return self.db.get(Currency, code.upper())

    def get_active(self, code: str) -> Optional[Currency]:
        currency = self.get(code)
        return currency if currency and currency.is_active else None

    def list_active(self) -> List[Currency]:
        stmt = select(Currency).where(Currency.is_active).order_by(Currency.code)
        return list(self.db.scalars(stmt).all())

    def create(self, code: str, name: str, symbol: str, exchange_rate_to_base: float) -> Currency:
        currency = Currency(
            code=code.upper(), name=name, symbol=symbol, exchange_rate_to_base=exchange_rate_to_base
        )
        self.db.add(currency)
        self.db.commit()
        self.db.refresh(currency)
        return currency

    def update_rate(self, currency: Currency, exchange_rate_to_base: float) -> Currency:
        currency.exchange_rate_to_base = exchange_rate_to_base
        self.db.commit()
        self.db.refresh(currency)
        return currency

    def set_active(self, currency: Currency, is_active: bool) -> Currency:
        currency.is_active = is_active
        self.db.commit()
        self.db.refresh(currency)
        return currency
