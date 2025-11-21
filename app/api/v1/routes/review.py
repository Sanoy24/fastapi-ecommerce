from typing import Annotated, List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_review_service_dep
from app.schema.review_schema import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schema.user_schema import UserPublic
from app.services.order_service import OrderService

router = APIRouter(tags=["Reviews"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
review_dependency = Annotated[OrderService, Depends(get_review_service_dep)]


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review: ReviewCreate,
    review_service: review_dependency,
    current_user: user_dependency,
):
    """
    Create a new review for a product.
    """

    return review_service.create_review(review=review, user_id=current_user.id)


@router.get("/product/{product_id}", response_model=List[ReviewResponse])
def get_reviews_by_product(
    product_id: int,
    review_service: review_dependency,
    skip: int = 0,
    limit: int = 100,
):
    """
    Get all reviews for a specific product.
    """
    return review_service.get_reviews_by_product(
        product_id=product_id, skip=skip, limit=limit
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: int,
    review_service: review_dependency,
):
    """
    Get a specific review by ID.
    """
    return review_service.get_review(review_id=review_id)


@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: int,
    review_update: ReviewUpdate,
    review_service: review_dependency,
    current_user: user_dependency,
):
    """
    Update a review. Only the owner of the review can update it.
    """

    return review_service.update_review(
        review_id=review_id, review_update=review_update, current_user=current_user
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    review_service: review_dependency,
    current_user: user_dependency,
):
    """
    Delete a review. Only the owner or an admin can delete it.
    """
    review_service.delete_review(review_id=review_id, current_user=current_user)
