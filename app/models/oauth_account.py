from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class OAuthAccount(Base):
    """Links a third-party identity (Google/Facebook) to a local User.

    The identity-link table social login needs: one User can sign in
    through multiple providers (each gets its own row here), and one
    provider identity must resolve to exactly one User — enforced by the
    (provider, provider_user_id) unique constraint. The (user_id, provider)
    constraint keeps at most one linked account per provider per user,
    which is what UserService.link_oauth_account/unlink_oauth_account
    assume.
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_account_provider_identity"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_account_user_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    # The email the provider reported at link time — kept for display/audit,
    # not treated as authoritative afterward (the user's own User.email is).
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.current_timestamp())

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")
