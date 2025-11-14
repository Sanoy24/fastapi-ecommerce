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


@router.post(
    "/register",
    response_model=UserPublic,
    summary="Register user",
    description="Create a new user account.",
)
async def create_user(
    create_user_data: CreateUserSchema,
    user_service: user_dependency,
) -> UserPublic:
    """Register a new user and return public profile."""
    user = user_service.create_user(create_user_data)
    return user


@router.post(
    "/login",
    response_model=TokenSchema,
    summary="Login",
    description="Authenticate a user and return a JWT token.",
)
async def login(
    user_login_data: LoginSchema, user_service: user_dependency
) -> TokenSchema:
    """Log in and return access token."""
    return user_service.login(user_login_data=user_login_data)


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user",
    description="Returns the currently authenticated user's profile.",
)
async def get_user(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
) -> UserPublic:
    """Return current authenticated user profile."""
    return current_user


@router.put(
    "/me",
    response_model=UserPublic,
    summary="Update current user",
    description="Update the current user's profile.",
)
async def update_user(
    update_user_data: UpdateUserSchema,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
) -> UserPublic:
    """Update current user's profile."""
    updated_user = user_service.update_user(
        id=current_user.id, update_user_data=update_user_data
    )
    return updated_user


@router.delete(
    "/me",
    response_model=DeleteUserResponseModel,
    summary="Delete current user",
    description="Delete the currently authenticated user's account.",
)
async def delete_user(
    current_user: Annotated[require_admin, Depends()],
    user_service: user_dependency,
) -> DeleteUserResponseModel:
    """Delete current user account."""
    user_service.delete_user(id=current_user.id)
    return {"detail": "User deleted successfully"}


@router.post(
    "/me/address",
    response_model=AddressPublic,
    summary="Add address",
    description="Add a new address to the current user.",
)
async def add_address_to_user(
    address_data: AddressCreate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    address_service: address_depedency,
) -> AddressPublic:
    """Add address to current user's account."""
    user_id = current_user.id
    is_first = False
    if not current_user.addresses:
        is_first = True
    address = address_service.add_address(user_id, is_first, address_data=address_data)
    return address


@router.put(
    "/me/address/{address_id}",
    response_model=AddressPublic,
    summary="Update address",
    description="Update an existing address for the current user.",
)
async def update_address(
    address_data: AddressUpdate,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    address_service: address_depedency,
    address_id: int,
) -> AddressPublic:
    """Update an address belonging to the current user."""
    if not address_data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    address = address_service.update_address(address_id, address_data)
    return address
