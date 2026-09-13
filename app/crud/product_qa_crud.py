from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.product_answer import ProductAnswer
from app.models.product_question import ProductQuestion


class ProductQACrud:
    def __init__(self, db: Session):
        self.db = db

    def create_question(self, product_id: int, user_id: int, question: str) -> ProductQuestion:
        db_question = ProductQuestion(product_id=product_id, user_id=user_id, question=question)
        self.db.add(db_question)
        self.db.commit()
        self.db.refresh(db_question)
        return db_question

    def get_questions_by_product(
        self, product_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductQuestion]:
        stmt = (
            select(ProductQuestion)
            .where(ProductQuestion.product_id == product_id)
            .options(selectinload(ProductQuestion.answers))
            .order_by(ProductQuestion.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def get_question(self, question_id: int) -> Optional[ProductQuestion]:
        return self.db.get(ProductQuestion, question_id)

    def delete_question(self, question: ProductQuestion) -> None:
        self.db.delete(question)
        self.db.commit()

    def create_answer(self, question_id: int, user_id: int, answer: str) -> ProductAnswer:
        db_answer = ProductAnswer(question_id=question_id, user_id=user_id, answer=answer)
        self.db.add(db_answer)
        self.db.commit()
        self.db.refresh(db_answer)
        return db_answer

    def get_answer(self, answer_id: int) -> Optional[ProductAnswer]:
        return self.db.get(ProductAnswer, answer_id)

    def delete_answer(self, answer: ProductAnswer) -> None:
        self.db.delete(answer)
        self.db.commit()
