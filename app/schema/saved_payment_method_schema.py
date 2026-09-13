from datetime import datetime

from pydantic import BaseModel


class SetupIntentResponse(BaseModel):
    """client_secret for Stripe.js to collect card details against and
    confirm client-side — the backend never sees the card itself."""

    client_secret: str


class SavePaymentMethodRequest(BaseModel):
    # The PaymentMethod id Stripe.js produced after confirming the
    # SetupIntent from create_setup_intent — never a raw card number.
    payment_method_id: str
    set_default: bool = False


class SavedPaymentMethodResponse(BaseModel):
    id: int
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime

    model_config = {"from_attributes": True}
