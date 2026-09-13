from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_saved_payment_method_service_dep
from app.schema.saved_payment_method_schema import (
    SavePaymentMethodRequest,
    SavedPaymentMethodResponse,
    SetupIntentResponse,
)
from app.schema.user_schema import UserPublic
from app.services.saved_payment_method_service import SavedPaymentMethodService

router = APIRouter(tags=["Saved Payment Methods"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
service_dependency = Annotated[SavedPaymentMethodService, Depends(get_saved_payment_method_service_dep)]


@router.post(
    "/setup-intent",
    response_model=SetupIntentResponse,
    summary="Start saving a card",
)
def create_setup_intent(
    service: service_dependency,
    current_user: user_dependency,
):
    """Returns a Stripe SetupIntent client_secret for Stripe.js to collect
    and confirm card details against client-side. The backend never
    receives a raw card number — only the resulting PaymentMethod id,
    which the frontend then passes to POST /payments/methods."""
    return service.create_setup_intent(current_user.id)


@router.post("", response_model=SavedPaymentMethodResponse, status_code=status.HTTP_201_CREATED)
def save_payment_method(
    request: SavePaymentMethodRequest,
    service: service_dependency,
    current_user: user_dependency,
):
    """Attach a PaymentMethod (from a confirmed SetupIntent) to this
    account for reuse at future checkouts."""
    return service.save_payment_method(
        user_id=current_user.id,
        payment_method_id=request.payment_method_id,
        set_default=request.set_default,
    )


@router.get("", response_model=List[SavedPaymentMethodResponse])
def list_payment_methods(
    service: service_dependency,
    current_user: user_dependency,
):
    return service.list_methods(current_user.id)


@router.post("/{method_id}/default", response_model=SavedPaymentMethodResponse)
def set_default_payment_method(
    method_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    return service.set_default(current_user.id, method_id)


@router.delete("/{method_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payment_method(
    method_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    """Detaches the card from Stripe and removes our record of it. If it
    was the default, the oldest remaining saved card (if any) becomes the
    new default."""
    service.delete_method(current_user.id, method_id)
