from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, require_admin
from app.schema.review_schema import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schema.user_schema import UserPublic
from app.crud import review as review_crud

router = APIRouter(tags=["Reviews"])


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_review(
    review: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user),
):
    """
    Create a new review for a product.
    """
    return review_crud.create_review(db=db, review=review, user_id=current_user.id)


@router.get("/product/{product_id}", response_model=List[ReviewResponse])
def get_reviews_by_product(
    product_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    Get all reviews for a specific product.
    """
    return review_crud.get_reviews_by_product(
        db=db, product_id=product_id, skip=skip, limit=limit
    )


@router.get("/{review_id}", response_model=ReviewResponse)
def get_review(
    review_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a specific review by ID.
    """
    review = review_crud.get_review(db=db, review_id=review_id)
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
        )
    return review


@router.put("/{review_id}", response_model=ReviewResponse)
def update_review(
    review_id: int,
    review_update: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user),
):
    """
    Update a review. Only the owner of the review can update it.
    """
    db_review = review_crud.get_review(db=db, review_id=review_id)
    if not db_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
        )
    
    if db_review.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this review",
        )

    return review_crud.update_review(
        db=db, db_review=db_review, review_update=review_update
    )


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: UserPublic = Depends(get_current_user),
):
    """
    Delete a review. Only the owner or an admin can delete it.
    """
    db_review = review_crud.get_review(db=db, review_id=review_id)
    if not db_review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
        )

    if db_review.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this review",
        )

    review_crud.delete_review(db=db, db_review=db_review)
