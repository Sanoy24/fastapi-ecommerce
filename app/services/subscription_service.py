from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import OrderException
from app.crud.saved_payment_method_crud import SavedPaymentMethodCrud
from app.crud.subscription import SubscriptionCrud
from app.models.product import Product
from app.models.subscription import Subscription
from app.schema.subscription_schema import SubscriptionCreate, SubscriptionResponse
from app.utils.subscription_billing import compute_next_billing_date
from app.utils.time import utcnow


class SubscriptionService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = SubscriptionCrud(db)
        self.saved_payment_method_crud = SavedPaymentMethodCrud(db)

    def create_subscription(self, user_id: int, dto: SubscriptionCreate) -> SubscriptionResponse:
        product = self.db.get(Product, dto.product_id)
        if not product or product.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        if dto.variant_id is not None:
            from app.models.product_variant import ProductVariant

            variant = self.db.get(ProductVariant, dto.variant_id)
            if not variant or variant.product_id != dto.product_id:
                raise HTTPException(status_code=404, detail="Variant not found for this product")

        payment_method = self.saved_payment_method_crud.get_by_id(dto.saved_payment_method_id)
        if not payment_method or payment_method.user_id != user_id:
            raise HTTPException(status_code=404, detail="Saved payment method not found")

        try:
            self.crud.order_crud.validate_address(user_id, dto.shipping_address_id)
            self.crud.order_crud.validate_address(user_id, dto.billing_address_id)
        except OrderException as e:
            raise HTTPException(status_code=400, detail=str(e))

        next_billing_date = compute_next_billing_date(dto.interval, from_dt=utcnow())
        subscription = self.crud.create(user_id, dto, next_billing_date)
        return SubscriptionResponse.model_validate(subscription)

    def list_subscriptions(self, user_id: int) -> List[SubscriptionResponse]:
        return [SubscriptionResponse.model_validate(s) for s in self.crud.list_for_user(user_id)]

    def get_subscription(self, user_id: int, subscription_id: int) -> SubscriptionResponse:
        return SubscriptionResponse.model_validate(self._get_owned(user_id, subscription_id))

    def pause_subscription(self, user_id: int, subscription_id: int) -> SubscriptionResponse:
        subscription = self._get_owned(user_id, subscription_id)
        if subscription.status != "active":
            raise HTTPException(
                status_code=400, detail=f"Only active subscriptions can be paused. Current status: '{subscription.status}'."
            )
        return SubscriptionResponse.model_validate(self.crud.pause(subscription))

    def resume_subscription(self, user_id: int, subscription_id: int) -> SubscriptionResponse:
        subscription = self._get_owned(user_id, subscription_id)
        if subscription.status != "paused":
            raise HTTPException(
                status_code=400, detail=f"Only paused subscriptions can be resumed. Current status: '{subscription.status}'."
            )
        next_billing_date = compute_next_billing_date(subscription.interval, from_dt=utcnow())
        return SubscriptionResponse.model_validate(self.crud.resume(subscription, next_billing_date))

    def skip_next_billing(self, user_id: int, subscription_id: int) -> SubscriptionResponse:
        """Push the next charge out by one full interval without pausing —
        for "not this month, but keep the subscription going"."""
        subscription = self._get_owned(user_id, subscription_id)
        if subscription.status not in ("active", "past_due"):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot skip a billing cycle for a subscription that is '{subscription.status}'.",
            )
        next_billing_date = compute_next_billing_date(subscription.interval, from_dt=subscription.next_billing_date)
        return SubscriptionResponse.model_validate(self.crud.skip_next(subscription, next_billing_date))

    def cancel_subscription(self, user_id: int, subscription_id: int) -> None:
        subscription = self._get_owned(user_id, subscription_id)
        if subscription.status == "cancelled":
            raise HTTPException(status_code=400, detail="Subscription is already cancelled")
        self.crud.cancel(subscription)

    def _get_owned(self, user_id: int, subscription_id: int) -> Subscription:
        subscription = self.crud.get_by_id(subscription_id)
        if not subscription or subscription.user_id != user_id:
            raise HTTPException(status_code=404, detail="Subscription not found")
        return subscription
