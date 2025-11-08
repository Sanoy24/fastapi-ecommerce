from app.schema.address_schema import AddressCreate, AddressUpdate, AddressPublic
from app.services.address_service import AddressService
from fastapi import APIRouter, Depends, HTTPException
from app.services.user_service import UserService
from app.schema.user_schema import (
    CreateUserSchema,
    LoginSchema,
    TokenSchema,
    UserPublic,
    UpdateUserSchema,
    DeleteUserResponseModel,
)
from app.dependencies import (
    get_user_service_dep,
    get_current_user,
    require_admin,
    get_address_service_dep,
)
from typing import Annotated


router = APIRouter(tags=["User"])
user_dependency = Annotated[UserService, Depends(get_user_service_dep)]
address_depedency = Annotated[AddressService, Depends(get_address_service_dep)]


@router.post("/register", response_model=UserPublic)
async def create_user(
    create_user_data: CreateUserSchema,
    user_service: user_dependency,
) -> UserPublic:
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
) -> UserPublic:
    return current_user


@router.put("/me", response_model=UserPublic)
async def update_user(
    update_user_data: UpdateUserSchema,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
) -> UserPublic:
    updated_user = user_service.update_user(
        id=current_user.id, update_user_data=update_user_data
    )
    return updated_user


@router.delete("/me", response_model=DeleteUserResponseModel)
async def delete_user(
    current_user: Annotated[require_admin, Depends()],
    user_service: user_dependency,
) -> DeleteUserResponseModel:
    user_service.delete_user(id=current_user.id)
    return {"detail": "User deleted successfully"}


@router.post("/me/address", response_model=AddressPublic)
async def add_address_to_user(
    address_data: AddressCreate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    address_service: address_depedency,
) -> AddressPublic:
    user_id = current_user.id
    is_first = False
    if not current_user.addresses:
        is_first = True
    address = address_service.add_address(user_id, is_first, address_data=address_data)
    return address


@router.put("/me/address/{address_id}", response_model=AddressPublic)
async def update_address(
    address_data: AddressUpdate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    address_service: address_depedency,
    address_id: int,
) -> AddressPublic:
    if not address_data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    address = address_service.update_address(address_id, address_data)
    return address
