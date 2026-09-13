from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.crud.product_qa_crud import ProductQACrud
from app.models.product_answer import ProductAnswer
from app.models.product_question import ProductQuestion
from app.models.product import Product
from app.schema.user_schema import UserPublic


class ProductQAService:
    def __init__(self, db: Session):
        self.db = db
        self.crud = ProductQACrud(db)

    def ask_question(self, product_id: int, user_id: int, question: str) -> ProductQuestion:
        if not self.db.get(Product, product_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return self.crud.create_question(product_id=product_id, user_id=user_id, question=question)

    def list_questions(self, product_id: int, skip: int = 0, limit: int = 100) -> List[ProductQuestion]:
        return self.crud.get_questions_by_product(product_id=product_id, skip=skip, limit=limit)

    def get_question(self, question_id: int) -> ProductQuestion:
        question = self.crud.get_question(question_id)
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
        return question

    def delete_question(self, question_id: int, current_user: UserPublic) -> None:
        question = self.get_question(question_id)
        if question.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this question",
            )
        self.crud.delete_question(question)

    def answer_question(self, question_id: int, user_id: int, answer: str) -> ProductAnswer:
        self.get_question(question_id)  # 404s if the question doesn't exist
        return self.crud.create_answer(question_id=question_id, user_id=user_id, answer=answer)

    def delete_answer(self, answer_id: int, current_user: UserPublic) -> None:
        answer = self.crud.get_answer(answer_id)
        if not answer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Answer not found")
        if answer.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this answer",
            )
        self.crud.delete_answer(answer)
