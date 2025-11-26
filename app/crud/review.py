from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select
from typing import List, Optional

from app.models.product import Product
from app.models.review import Review
from app.models.user import User
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

    def total_reviews(self):
        total_reviews = self.db.query(func.count(Review.id)).scalar() or 0
        return total_reviews

    def pending_reviews(self):
        pending_reviews = (
            self.db.query(func.count(Review.id))
            .filter(Review.is_approved == False)
            .scalar()
            or 0
        )
        return pending_reviews

    def approved_reviews(self):
        approved_reviews = (
            self.db.query(func.count(Review.id))
            .filter(Review.is_approved == True)
            .scalar()
            or 0
        )
        return approved_reviews

    def average_rating(self):
        average_rating = self.db.query(func.avg(Review.rating)).scalar()
        return average_rating

    def get_pending_reviews(self, page: int = 1, page_size: int = 20):
        """Get paginated list of pending reviews"""
        query = (
            self.db.query(Review)
            .join(User, Review.user_id == User.id)
            .join(Product, Review.product_id == Product.id)
            .filter(Review.is_approved == False)
        )

        total = query.count()

        offset = (page - 1) * page_size
        reviews = (
            query.order_by(Review.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return total, reviews

    def get_all_reviews(self, page: int = 1, page_size: int = 20):
        """Get paginated list of all reviews"""
        query = (
            self.db.query(Review)
            .join(User, Review.user_id == User.id)
            .join(Product, Review.product_id == Product.id)
        )

        total = query.count()

        offset = (page - 1) * page_size
        reviews = (
            query.order_by(Review.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return total, reviews

    def approve_review(self, review_id: int) -> Review:
        """Approve a review"""
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        review.is_approved = True
        self.db.commit()
        self.db.refresh(review)
        return review

    def reject_review(self, review_id: int) -> None:
        """Reject/delete a review"""
        review = self.db.query(Review).filter(Review.id == review_id).first()
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Review not found"
            )

        self.db.delete(review)
        self.db.commit()
