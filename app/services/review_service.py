from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud.review import ReviewCrud
from app.models.review import Review
from app.schema.review_schema import ReviewCreate, ReviewResponse, ReviewUpdate
from app.schema.user_schema import UserPublic


class ReviewService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = ReviewCrud(db=db)

    def create_review(self, review: ReviewCreate, user_id: int) -> ReviewResponse:
        """Create a new review."""
        db_review = self.crud.create_review(review=review, user_id=user_id)
        return db_review

    def get_reviews_by_product(
        self, product_id: int, skip: int = 0, limit: int = 100
    ) -> List[ReviewResponse]:
        """Get all reviews for a specific product."""
        reviews = self.crud.get_reviews_by_product(
            product_id=product_id, skip=skip, limit=limit
        )
        return reviews

    def get_review(self, review_id: int) -> ReviewResponse:
        """Get a specific review by ID."""
        review = self.crud.get_review(review_id=review_id)
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )
        return review

    def update_review(
        self, review_id: int, review_update: ReviewUpdate, current_user: UserPublic
    ) -> ReviewResponse:
        """Update a review."""
        db_review = self.crud.get_review(review_id=review_id)
        if not db_review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        if db_review.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this review",
            )

        updated_review = self.crud.update_review(
            db_review=db_review, review_update=review_update
        )
        return updated_review

    def delete_review(self, review_id: int, current_user: UserPublic) -> None:
        """Delete a review."""
        db_review = self.crud.get_review(review_id=review_id)
        if not db_review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        if db_review.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this review",
            )

        self.crud.delete_review(db_review=db_review)
