from fastapi import APIRouter, Depends
from app.schema.user_schema import (
    CreateUserSchema,
    LoginSchema,
    TokenSchema,
    UserPublic,
)
from app.dependencies import get_user_service_dep, get_current_user
from app.services.user_service import UserService
from typing import Annotated
from app.models.user import User

router = APIRouter(tags=["User"])
user_dependency = Annotated[UserService, Depends(get_user_service_dep)]


@router.post("/register")
async def create_user(
    create_user_data: CreateUserSchema,
    user_service: user_dependency,
):
    user = user_service.create_user(create_user_data)
    return user


@router.post("/login", response_model=TokenSchema)
async def login(
    user_login_data: LoginSchema, user_service: user_dependency
) -> TokenSchema:
    return user_service.login(user_login_data=user_login_data)


@router.get("/me", response_model=UserPublic)
async def get_user(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
):
    return current_user
