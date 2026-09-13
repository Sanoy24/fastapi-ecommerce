from datetime import datetime

from pydantic import BaseModel, Field


class CurrencyCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=3, description="ISO 4217 code, e.g. EUR")
    name: str = Field(..., max_length=50)
    symbol: str = Field(..., max_length=5)
    exchange_rate_to_base: float = Field(..., gt=0, description="Units of this currency per 1 unit of the base currency")


class CurrencyUpdateRate(BaseModel):
    exchange_rate_to_base: float = Field(..., gt=0)


class CurrencyResponse(BaseModel):
    code: str
    name: str
    symbol: str
    exchange_rate_to_base: float
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SetCartCurrencyRequest(BaseModel):
    currency_code: str = Field(..., min_length=3, max_length=3)
