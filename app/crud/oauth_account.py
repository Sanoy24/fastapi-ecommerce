from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.oauth_account import OAuthAccount


class OAuthAccountCrud:
    def __init__(self, db: Session):
        self.db = db

    def get_by_provider_identity(self, provider: str, provider_user_id: str) -> Optional[OAuthAccount]:
        return self.db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        ).first()

    def get_for_user_and_provider(self, user_id: int, provider: str) -> Optional[OAuthAccount]:
        return self.db.scalars(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id, OAuthAccount.provider == provider
            )
        ).first()

    def list_for_user(self, user_id: int) -> List[OAuthAccount]:
        stmt = select(OAuthAccount).where(OAuthAccount.user_id == user_id).order_by(OAuthAccount.created_at)
        return list(self.db.scalars(stmt).all())

    def create(self, user_id: int, provider: str, provider_user_id: str, email: str) -> OAuthAccount:
        account = OAuthAccount(
            user_id=user_id, provider=provider, provider_user_id=provider_user_id, email=email
        )
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def delete(self, account: OAuthAccount) -> None:
        self.db.delete(account)
        self.db.commit()
