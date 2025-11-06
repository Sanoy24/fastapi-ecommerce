from fastapi import APIRouter, Depends
from app.schema.user_schema import (
    CreateUserSchema,
    LoginSchema,
    TokenSchema,
    UserPublic,
    UpdateUserSchema,
)
from app.crud.address import AddressCrud
from app.schema.address_schema import AddressCreate
from app.dependencies import (
    get_user_service_dep,
    get_current_user,
    require_admin,
    get_address_service_dep,
)
from app.services.user_service import UserService
from app.services.address_service import AddressService
from typing import Annotated
from app.models.user import User

router = APIRouter(tags=["User"])
user_dependency = Annotated[UserService, Depends(get_user_service_dep)]
address_depedency = Annotated[AddressService, Depends(get_address_service_dep)]


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


@router.put("/me", response_model=UserPublic)
async def update_user(
    update_user_data: UpdateUserSchema,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
):
    updated_user = user_service.update_user(
        id=current_user.id, update_user_data=update_user_data
    )
    return updated_user


@router.delete("/me")
async def delete_user(
    current_user: Annotated[require_admin, Depends()],
    user_service: user_dependency,
):
    user_service.delete_user(id=current_user.id)
    return {"detail": "User deleted successfully"}


@router.post("/me/address")
async def add_address_to_user(
    address_data: AddressCreate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    address_service: address_depedency,
):
    user_id = current_user.id
    address = address_service.add_address(user_id, address_data=address_data)
    return address
