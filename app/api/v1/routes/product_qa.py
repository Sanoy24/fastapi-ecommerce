from typing import Annotated, List

from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_user, get_product_qa_service_dep
from app.schema.product_qa_schema import (
    ProductAnswerCreate,
    ProductAnswerResponse,
    ProductQuestionCreate,
    ProductQuestionResponse,
)
from app.schema.user_schema import UserPublic
from app.services.product_qa_service import ProductQAService

router = APIRouter(tags=["Product Q&A"])

user_dependency = Annotated[UserPublic, Depends(get_current_user)]
qa_dependency = Annotated[ProductQAService, Depends(get_product_qa_service_dep)]


@router.post("", response_model=ProductQuestionResponse, status_code=status.HTTP_201_CREATED)
def ask_question(
    question: ProductQuestionCreate,
    qa_service: qa_dependency,
    current_user: user_dependency,
):
    """Ask a question about a product. Open to any signed-in user, not
    gated on having purchased it — people ask to decide whether to buy."""
    return qa_service.ask_question(
        product_id=question.product_id, user_id=current_user.id, question=question.question
    )


@router.get("/product/{product_id}", response_model=List[ProductQuestionResponse])
def get_questions_by_product(
    product_id: int,
    qa_service: qa_dependency,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
):
    """List questions (with their answers) for a product, newest first."""
    return qa_service.list_questions(product_id=product_id, skip=skip, limit=limit)


@router.get("/{question_id}", response_model=ProductQuestionResponse)
def get_question(
    question_id: int,
    qa_service: qa_dependency,
):
    return qa_service.get_question(question_id=question_id)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    qa_service: qa_dependency,
    current_user: user_dependency,
):
    """Delete a question (and its answers). Only the asker or an admin."""
    qa_service.delete_question(question_id=question_id, current_user=current_user)


@router.post(
    "/{question_id}/answers", response_model=ProductAnswerResponse, status_code=status.HTTP_201_CREATED
)
def answer_question(
    question_id: int,
    answer: ProductAnswerCreate,
    qa_service: qa_dependency,
    current_user: user_dependency,
):
    """Answer a question. Crowd-sourced — any signed-in user can answer,
    not just an admin/seller."""
    return qa_service.answer_question(question_id=question_id, user_id=current_user.id, answer=answer.answer)


@router.delete("/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_answer(
    answer_id: int,
    qa_service: qa_dependency,
    current_user: user_dependency,
):
    """Delete an answer. Only the person who wrote it or an admin."""
    qa_service.delete_answer(answer_id=answer_id, current_user=current_user)
