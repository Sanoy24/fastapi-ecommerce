from pydantic import BaseModel, EmailStr
from typing import Optional


class CreateUserSchema(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: str


class UserPublic(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    phone: str

    model_config = {"from_attributes": True}


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class TokenSchema(BaseModel):
    token: str
    token_type: str
