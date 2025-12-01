from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from app.models.wishlist import Wishlist
from app.models.product import Product
from app.models.user import User


class WishlistCrud:
    """CRUD operations for wishlist"""

    def __init__(self, db: Session):
        self.db = db

    def add_to_wishlist(self, user_id: int, product_id: int) -> Optional[Wishlist]:
        """
        Add a product to user's wishlist
        Returns None if already exists (due to unique constraint)
        """
        try:
            wishlist_item = Wishlist(user_id=user_id, product_id=product_id)
            self.db.add(wishlist_item)
            self.db.commit()
            self.db.refresh(wishlist_item)
            return wishlist_item
        except IntegrityError:
            # Product already in wishlist
            self.db.rollback()
            return None

    def remove_from_wishlist(self, user_id: int, product_id: int) -> bool:
        """
        Remove a product from user's wishlist
        Returns True if removed, False if not found
        """
        stmt = select(Wishlist).where(
            and_(Wishlist.user_id == user_id, Wishlist.product_id == product_id)
        )
        wishlist_item = self.db.scalar(stmt)

        if wishlist_item:
            self.db.delete(wishlist_item)
            self.db.commit()
            return True
        return False

    def get_user_wishlist(self, user_id: int) -> List[Wishlist]:
        """Get all wishlist items for a user"""
        stmt = (
            select(Wishlist)
            .where(Wishlist.user_id == user_id)
            .order_by(Wishlist.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def is_in_wishlist(self, user_id: int, product_id: int) -> bool:
        """Check if a product is in user's wishlist"""
        stmt = select(Wishlist).where(
            and_(Wishlist.user_id == user_id, Wishlist.product_id == product_id)
        )
        return self.db.scalar(stmt) is not None

    def get_wishlist_count(self, user_id: int) -> int:
        """Get count of items in user's wishlist"""
        stmt = select(Wishlist).where(Wishlist.user_id == user_id)
        return len(list(self.db.scalars(stmt).all()))

    def clear_wishlist(self, user_id: int) -> int:
        """
        Clear all items from user's wishlist
        Returns number of items removed
        """
        stmt = select(Wishlist).where(Wishlist.user_id == user_id)
        items = list(self.db.scalars(stmt).all())
        count = len(items)

        for item in items:
            self.db.delete(item)

        self.db.commit()
        return count

    def get_wishlist_item(self, user_id: int, product_id: int) -> Optional[Wishlist]:
        """Get a specific wishlist item"""
        stmt = select(Wishlist).where(
            and_(Wishlist.user_id == user_id, Wishlist.product_id == product_id)
        )
        return self.db.scalar(stmt)
