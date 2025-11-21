from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from app.models.review import Review
from app.schema.review_schema import ReviewCreate, ReviewUpdate


class ReviewCrud:
    def __init__(self, db: Session):
        self.db = db

    def create_review(self, review: ReviewCreate, user_id: int) -> Review:
        db_review = Review(
            user_id=user_id,
            product_id=review.product_id,
            rating=review.rating,
            comment=review.comment,
        )
        self.db.add(db_review)
        self.db.commit()
        self.db.refresh(db_review)
        return db_review

    def get_reviews_by_product(
        self, product_id: int, skip: int = 0, limit: int = 100
    ) -> List[Review]:
        stmt = (
            select(Review)
            .where(Review.product_id == product_id)
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_review(self, review_id: int) -> Optional[Review]:
        return self.db.get(Review, review_id)

    def update_review(self, db_review: Review, review_update: ReviewUpdate) -> Review:
        if review_update.rating is not None:
            db_review.rating = review_update.rating
        if review_update.comment is not None:
            db_review.comment = review_update.comment

        self.db.commit()
        self.db.refresh(db_review)
        return db_review

    def delete_review(self, db_review: Review) -> None:
        self.db.delete(db_review)
        self.db.commit()
