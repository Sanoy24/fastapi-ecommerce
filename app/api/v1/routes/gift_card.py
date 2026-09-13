from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud.gift_card_crud import GiftCardCrud
from app.dependencies import get_current_user, get_db, require_admin
from app.models.user import User
from app.schema.gift_card_schema import (
    GiftCardIssueRequest,
    GiftCardResponse,
    RedeemGiftCardRequest,
    StoreCreditBalanceResponse,
    StoreCreditTransactionListResponse,
)
from app.schema.user_schema import UserPublic
from app.services.admin_service import AdminService

router = APIRouter(prefix="/gift-cards", tags=["Gift Cards"])
admin_router = APIRouter(prefix="/admin/gift-cards", tags=["admin-gift-cards"])
wallet_router = APIRouter(prefix="/wallet", tags=["Store Credit"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]


@router.post("/redeem", response_model=GiftCardResponse, summary="Redeem a gift card code into store credit")
def redeem_gift_card(
    data: RedeemGiftCardRequest,
    current_user: user_dependency,
    db: Session = Depends(get_db),
):
    crud = GiftCardCrud(db)
    gift_card = crud.get_by_code(data.code)
    if not gift_card:
        raise HTTPException(status_code=404, detail="Gift card not found")

    user = db.get(User, current_user.id)
    assert user is not None  # current_user comes from a real, just-authenticated row
    return crud.redeem(gift_card, user)


@admin_router.post("", response_model=GiftCardResponse, status_code=status.HTTP_201_CREATED)
def issue_gift_card(
    data: GiftCardIssueRequest,
    db: Session = Depends(get_db),
    admin: UserPublic = Depends(require_admin),
):
    gift_card = GiftCardCrud(db).issue(data.value, data.note, data.expires_at, admin.id)
    AdminService(db).log_action(
        admin.id, "ISSUE_GIFT_CARD", "gift_card", gift_card.id,
        new_value={"code": gift_card.code, "value": data.value},
    )
    return gift_card


@admin_router.get("", response_model=List[GiftCardResponse])
def list_gift_cards(
    db: Session = Depends(get_db),
    admin: UserPublic = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    _total, gift_cards = GiftCardCrud(db).list_all(page, page_size)
    return gift_cards


@wallet_router.get("/balance", response_model=StoreCreditBalanceResponse)
def get_store_credit_balance(current_user: user_dependency):
    return StoreCreditBalanceResponse(balance=current_user.store_credit_balance)


@wallet_router.get("/transactions", response_model=StoreCreditTransactionListResponse)
def list_store_credit_transactions(
    current_user: user_dependency,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    total, transactions = GiftCardCrud(db).list_store_credit_transactions(current_user.id, page, page_size)
    return StoreCreditTransactionListResponse(total=total, page=page, page_size=page_size, transactions=transactions)
