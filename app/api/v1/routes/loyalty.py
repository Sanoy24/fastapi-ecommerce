from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.crud.loyalty_crud import LoyaltyCrud
from app.dependencies import get_current_user, get_db
from app.schema.loyalty_schema import LoyaltyBalanceResponse, LoyaltyTransactionListResponse
from app.schema.user_schema import UserPublic

router = APIRouter(prefix="/loyalty", tags=["Loyalty Points"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]


@router.get("/balance", response_model=LoyaltyBalanceResponse)
def get_balance(current_user: user_dependency):
    return LoyaltyBalanceResponse(points_balance=current_user.loyalty_points_balance)


@router.get("/transactions", response_model=LoyaltyTransactionListResponse)
def list_transactions(
    current_user: user_dependency,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, transactions = LoyaltyCrud(db).list_transactions(current_user.id, page, page_size)
    return LoyaltyTransactionListResponse(total=total, page=page, page_size=page_size, transactions=transactions)
