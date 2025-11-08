from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from .address_schema import AddressPublic


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
    addresses: list[AddressPublic] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserSchema(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)

    model_config = {"from_attributes": True}


class DeleteUserResponseModel(BaseModel):
    detail: str
