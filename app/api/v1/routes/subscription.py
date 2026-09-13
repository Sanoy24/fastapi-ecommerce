from typing import Annotated, List

from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user, get_subscription_service_dep
from app.schema.subscription_schema import SubscriptionCreate, SubscriptionResponse
from app.schema.user_schema import UserPublic
from app.services.subscription_service import SubscriptionService

router = APIRouter(tags=["Subscriptions"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
service_dependency = Annotated[SubscriptionService, Depends(get_subscription_service_dep)]


@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
def create_subscription(
    dto: SubscriptionCreate,
    service: service_dependency,
    current_user: user_dependency,
):
    """Start a recurring order for one product at a fixed quantity and
    interval, charged automatically against a saved payment method."""
    return service.create_subscription(current_user.id, dto)


@router.get("", response_model=List[SubscriptionResponse])
def list_subscriptions(
    service: service_dependency,
    current_user: user_dependency,
):
    return service.list_subscriptions(current_user.id)


@router.get("/{subscription_id}", response_model=SubscriptionResponse)
def get_subscription(
    subscription_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    return service.get_subscription(current_user.id, subscription_id)


@router.post("/{subscription_id}/pause", response_model=SubscriptionResponse)
def pause_subscription(
    subscription_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    return service.pause_subscription(current_user.id, subscription_id)


@router.post("/{subscription_id}/resume", response_model=SubscriptionResponse)
def resume_subscription(
    subscription_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    return service.resume_subscription(current_user.id, subscription_id)


@router.post(
    "/{subscription_id}/skip",
    response_model=SubscriptionResponse,
    summary="Skip the next billing cycle",
    description="Pushes the next charge out by one full interval without pausing the subscription.",
)
def skip_next_billing(
    subscription_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    return service.skip_next_billing(current_user.id, subscription_id)


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_subscription(
    subscription_id: int,
    service: service_dependency,
    current_user: user_dependency,
):
    service.cancel_subscription(current_user.id, subscription_id)
