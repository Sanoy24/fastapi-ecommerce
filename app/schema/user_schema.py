from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CreateUserSchema(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    token: str
    token_type: str


class UserPublic(BaseModel):
    id: int
    email: EmailStr
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    role: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
