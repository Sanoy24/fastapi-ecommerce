from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List

from app.crud.wishlist import WishlistCrud
from app.crud.product import ProductCrud
from app.crud.cart_item import CartCrud
from app.schema.wishlist_schema import (
    WishlistItemResponse,
    WishlistResponse,
    WishlistStatsResponse,
    WishlistActionResponse,
)


class WishlistService:
    """Service layer for wishlist operations"""

    def __init__(self, db: Session):
        self.db = db
        self.wishlist_crud = WishlistCrud(db=db)
        self.product_crud = ProductCrud(db=db)
        self.cart_crud = CartCrud(db=db)

    def add_product_to_wishlist(
        self, user_id: int, product_id: int
    ) -> WishlistActionResponse:
        """Add a product to user's wishlist"""
        # Check if product exists
        product = self.product_crud.get_product_by_id(product_id=product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        # Add to wishlist
        wishlist_item = self.wishlist_crud.add_to_wishlist(
            user_id=user_id, product_id=product_id
        )

        if wishlist_item is None:
            # Already in wishlist
            return WishlistActionResponse(
                message="Product is already in your wishlist", product_id=product_id
            )

        return WishlistActionResponse(
            message="Product added to wishlist successfully", product_id=product_id
        )

    def remove_product_from_wishlist(
        self, user_id: int, product_id: int
    ) -> WishlistActionResponse:
        """Remove a product from user's wishlist"""
        removed = self.wishlist_crud.remove_from_wishlist(
            user_id=user_id, product_id=product_id
        )

        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in wishlist",
            )

        return WishlistActionResponse(
            message="Product removed from wishlist successfully", product_id=product_id
        )

    def get_wishlist(self, user_id: int) -> WishlistResponse:
        """Get user's wishlist with product details"""
        wishlist_items = self.wishlist_crud.get_user_wishlist(user_id=user_id)

        items_response = []
        for item in wishlist_items:
            items_response.append(
                WishlistItemResponse(
                    id=item.id,
                    product_id=item.product.id,
                    product_name=item.product.name,
                    product_slug=item.product.slug,
                    product_price=float(item.product.price),
                    product_image_url=item.product.image_url,
                    product_stock_quantity=item.product.stock_quantity,
                    product_is_active=item.product.is_active,
                    added_at=item.created_at,
                )
            )

        return WishlistResponse(items=items_response, total_count=len(items_response))

    def get_wishlist_count(self, user_id: int) -> WishlistStatsResponse:
        """Get count of items in user's wishlist"""
        count = self.wishlist_crud.get_wishlist_count(user_id=user_id)
        return WishlistStatsResponse(count=count)

    def clear_wishlist(self, user_id: int) -> WishlistActionResponse:
        """Clear all items from user's wishlist"""
        count = self.wishlist_crud.clear_wishlist(user_id=user_id)
        return WishlistActionResponse(
            message=f"Wishlist cleared successfully. {count} item(s) removed."
        )

    def move_to_cart(self, user_id: int, product_id: int) -> WishlistActionResponse:
        """Move a wishlist item to shopping cart"""
        # Check if product is in wishlist
        wishlist_item = self.wishlist_crud.get_wishlist_item(
            user_id=user_id, product_id=product_id
        )
        if not wishlist_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found in wishlist",
            )

        # Check if product exists and is active
        product = self.product_crud.get_product_by_id(product_id=product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is not available",
            )

        if product.stock_quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is out of stock",
            )

        # Add to cart
        try:
            self.cart_crud.add_item_to_cart(
                user_id=user_id, product_id=product_id, quantity=1
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to add to cart: {str(e)}",
            )

        # Remove from wishlist
        self.wishlist_crud.remove_from_wishlist(user_id=user_id, product_id=product_id)

        return WishlistActionResponse(
            message="Product moved to cart successfully", product_id=product_id
        )

    def is_in_wishlist(self, user_id: int, product_id: int) -> bool:
        """Check if a product is in user's wishlist"""
        return self.wishlist_crud.is_in_wishlist(user_id=user_id, product_id=product_id)
