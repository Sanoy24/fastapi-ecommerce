from fastapi import APIRouter, Depends, status
from typing import Annotated

from app.dependencies import get_current_user, get_db
from app.services.wishlist_service import WishlistService
from app.schema.wishlist_schema import (
    AddToWishlistRequest,
    WishlistResponse,
    WishlistStatsResponse,
    WishlistActionResponse,
)
from app.schema.user_schema import UserPublic
from sqlalchemy.orm import Session

router = APIRouter(tags=["Wishlist"])


def get_wishlist_service(db: Annotated[Session, Depends(get_db)]) -> WishlistService:
    """Dependency to get wishlist service"""
    return WishlistService(db=db)


@router.get(
    "",
    response_model=WishlistResponse,
    summary="Get user's wishlist",
    description="Get all products in the authenticated user's wishlist",
)
async def get_wishlist(
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Get user's wishlist with product details"""
    return wishlist_service.get_wishlist(user_id=current_user.id)


@router.post(
    "",
    response_model=WishlistActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add product to wishlist",
    description="Add a product to the authenticated user's wishlist",
)
async def add_to_wishlist(
    request: AddToWishlistRequest,
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Add a product to wishlist"""
    return wishlist_service.add_product_to_wishlist(
        user_id=current_user.id, product_id=request.product_id
    )


@router.delete(
    "/{product_id}",
    response_model=WishlistActionResponse,
    summary="Remove product from wishlist",
    description="Remove a specific product from the authenticated user's wishlist",
)
async def remove_from_wishlist(
    product_id: int,
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Remove a product from wishlist"""
    return wishlist_service.remove_product_from_wishlist(
        user_id=current_user.id, product_id=product_id
    )


@router.delete(
    "",
    response_model=WishlistActionResponse,
    summary="Clear wishlist",
    description="Remove all products from the authenticated user's wishlist",
)
async def clear_wishlist(
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Clear entire wishlist"""
    return wishlist_service.clear_wishlist(user_id=current_user.id)


@router.get(
    "/count",
    response_model=WishlistStatsResponse,
    summary="Get wishlist count",
    description="Get the number of items in the authenticated user's wishlist",
)
async def get_wishlist_count(
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Get count of items in wishlist"""
    return wishlist_service.get_wishlist_count(user_id=current_user.id)


@router.post(
    "/{product_id}/move-to-cart",
    response_model=WishlistActionResponse,
    summary="Move wishlist item to cart",
    description="Move a product from wishlist to shopping cart",
)
async def move_to_cart(
    product_id: int,
    wishlist_service: Annotated[WishlistService, Depends(get_wishlist_service)],
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    """Move a wishlist item to shopping cart"""
    return wishlist_service.move_to_cart(user_id=current_user.id, product_id=product_id)
