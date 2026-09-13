from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.currency import CurrencyCrud
from app.dependencies import get_db, require_admin
from app.models.user import User
from app.schema.currency_schema import CurrencyCreate, CurrencyResponse, CurrencyUpdateRate
from app.services.admin_service import AdminService

router = APIRouter(prefix="/currencies", tags=["currencies"])
admin_router = APIRouter(prefix="/admin/currencies", tags=["admin-currencies"])


@router.get("", response_model=List[CurrencyResponse], summary="List currencies customers can check out in")
def list_currencies(db: Session = Depends(get_db)):
    return CurrencyCrud(db).list_active()


@admin_router.post("", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED)
def create_currency(
    data: CurrencyCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    crud = CurrencyCrud(db)
    if crud.get(data.code):
        raise HTTPException(status_code=400, detail=f"Currency '{data.code.upper()}' already exists")

    currency = crud.create(data.code, data.name, data.symbol, data.exchange_rate_to_base)
    AdminService(db).log_action(admin.id, "CREATE_CURRENCY", "currency", 0, new_value=data.model_dump())
    return currency


@admin_router.patch("/{code}/rate", response_model=CurrencyResponse, summary="Update a currency's exchange rate")
def update_currency_rate(
    code: str,
    data: CurrencyUpdateRate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    crud = CurrencyCrud(db)
    currency = crud.get(code)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")

    old_rate = float(currency.exchange_rate_to_base)
    updated = crud.update_rate(currency, data.exchange_rate_to_base)
    AdminService(db).log_action(
        admin.id, "UPDATE_CURRENCY_RATE", "currency", 0,
        old_value={"exchange_rate_to_base": old_rate},
        new_value={"exchange_rate_to_base": data.exchange_rate_to_base},
    )
    return updated


@admin_router.post("/{code}/activate", response_model=CurrencyResponse)
def activate_currency(
    code: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    crud = CurrencyCrud(db)
    currency = crud.get(code)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    return crud.set_active(currency, True)


@admin_router.post("/{code}/deactivate", response_model=CurrencyResponse)
def deactivate_currency(
    code: str,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Deactivating the base currency is refused — it's the anchor every
    other rate and every existing base-currency order/price is expressed
    against, so it must always be selectable."""
    from app.core.config import settings

    crud = CurrencyCrud(db)
    currency = crud.get(code)
    if not currency:
        raise HTTPException(status_code=404, detail="Currency not found")
    if currency.code == settings.BASE_CURRENCY_CODE:
        raise HTTPException(status_code=400, detail="Cannot deactivate the base currency")
    return crud.set_active(currency, False)
