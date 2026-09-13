from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ProductQuestionCreate(BaseModel):
    product_id: int
    question: str = Field(..., min_length=5, max_length=1000)


class ProductAnswerCreate(BaseModel):
    answer: str = Field(..., min_length=1, max_length=2000)


class ProductAnswerResponse(BaseModel):
    id: int
    question_id: int
    user_id: int
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductQuestionResponse(BaseModel):
    id: int
    product_id: int
    user_id: int
    question: str
    created_at: datetime
    answers: List[ProductAnswerResponse] = []

    model_config = {"from_attributes": True}
