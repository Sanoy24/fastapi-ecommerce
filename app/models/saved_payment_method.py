from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class SavedPaymentMethod(Base):
    """A card a customer has saved for reuse at checkout.

    Only ever stores what Stripe's PaymentMethod object returns for
    display (brand/last4/expiry) plus its id — never raw card data, which
    this app is not PCI-scoped to handle. Card collection happens
    client-side via Stripe Elements against a SetupIntent (see
    SavedPaymentMethodService.create_setup_intent); the backend only ever
    sees the resulting PaymentMethod id.
    """

    __tablename__ = "saved_payment_methods"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "stripe_payment_method_id", name="uq_saved_payment_method_user_pm"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stripe_payment_method_id: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # Exactly one row per user should have this set — enforced in
    # SavedPaymentMethodCrud (unset-then-set within one transaction), not a
    # DB constraint; a partial unique index expressing "at most one TRUE
    # per user_id" is more machinery than this invariant needs.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.current_timestamp())

    user: Mapped["User"] = relationship("User")
