from typing import List

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud.saved_payment_method_crud import SavedPaymentMethodCrud
from app.models.user import User
from app.schema.saved_payment_method_schema import SavedPaymentMethodResponse, SetupIntentResponse


class SavedPaymentMethodService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = SavedPaymentMethodCrud(db)

    def get_or_create_stripe_customer_id(self, user_id: int) -> str:
        """Every user gets at most one Stripe Customer, created the first
        time they try to save a card rather than at registration — most
        users never do."""
        existing = self.crud.get_user_stripe_customer_id(user_id)
        if existing:
            return existing

        user = self.db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        try:
            customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user_id)})
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        self.crud.set_user_stripe_customer_id(user_id, customer.id)
        return customer.id

    def create_setup_intent(self, user_id: int) -> SetupIntentResponse:
        """Start saving a card: the frontend collects card details via
        Stripe Elements and confirms this SetupIntent client-side, then
        calls save_payment_method with the resulting PaymentMethod id.
        Nothing here ever touches a raw card number."""
        customer_id = self.get_or_create_stripe_customer_id(user_id)
        try:
            intent = stripe.SetupIntent.create(
                customer=customer_id, automatic_payment_methods={"enabled": True}
            )
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return SetupIntentResponse(client_secret=intent.client_secret)

    def save_payment_method(
        self, user_id: int, payment_method_id: str, set_default: bool = False
    ) -> SavedPaymentMethodResponse:
        # Re-saving a card already on file is a no-op that returns the
        # existing row rather than erroring or duplicating it — the
        # frontend has no reliable way to know in advance whether a given
        # PaymentMethod id was already attached.
        existing = self.crud.get_by_stripe_payment_method_id(user_id, payment_method_id)
        if existing:
            if set_default and not existing.is_default:
                existing = self.crud.set_default(existing)
            return SavedPaymentMethodResponse.model_validate(existing)

        customer_id = self.get_or_create_stripe_customer_id(user_id)

        try:
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        except stripe.error.StripeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if payment_method.customer and payment_method.customer != customer_id:
            raise HTTPException(status_code=403, detail="This payment method does not belong to you")

        if payment_method.type != "card" or not payment_method.card:
            raise HTTPException(status_code=400, detail="Only card payment methods can be saved")

        if not payment_method.customer:
            try:
                stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
            except stripe.error.StripeError as e:
                raise HTTPException(status_code=400, detail=str(e))

        is_default = set_default or not self.crud.list_for_user(user_id)
        if is_default:
            self.crud.unset_default_for_user(user_id)

        saved = self.crud.create(
            user_id=user_id,
            stripe_payment_method_id=payment_method_id,
            brand=payment_method.card.brand,
            last4=payment_method.card.last4,
            exp_month=payment_method.card.exp_month,
            exp_year=payment_method.card.exp_year,
            is_default=is_default,
        )
        return SavedPaymentMethodResponse.model_validate(saved)

    def list_methods(self, user_id: int) -> List[SavedPaymentMethodResponse]:
        return [SavedPaymentMethodResponse.model_validate(m) for m in self.crud.list_for_user(user_id)]

    def set_default(self, user_id: int, method_id: int) -> SavedPaymentMethodResponse:
        method = self.crud.get_by_id(method_id)
        if not method or method.user_id != user_id:
            raise HTTPException(status_code=404, detail="Payment method not found")
        return SavedPaymentMethodResponse.model_validate(self.crud.set_default(method))

    def delete_method(self, user_id: int, method_id: int) -> None:
        method = self.crud.get_by_id(method_id)
        if not method or method.user_id != user_id:
            raise HTTPException(status_code=404, detail="Payment method not found")

        try:
            stripe.PaymentMethod.detach(method.stripe_payment_method_id)
        except stripe.error.StripeError:
            # Already detached (or gone) on Stripe's side shouldn't block
            # removing our own record of it.
            pass

        was_default = method.is_default
        self.crud.delete(method)
        if was_default:
            self.crud.promote_oldest_to_default(user_id)
