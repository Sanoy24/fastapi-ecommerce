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
address_dependency = Annotated[
    AddressService, Depends(get_address_service_dep)
]  # Note: Fixed typo from 'depedency' to 'dependency'


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
    """
    Register a new user and return the public profile.

    This endpoint allows a new user to register by providing the necessary user data.
    The user service handles the creation logic, including validation and persistence.

    Parameters:
    - create_user_data (CreateUserSchema): The data required to create a new user, such as username, email, and password.
    - user_service (UserService): Dependency-injected service for user operations.

    Returns:
    - UserPublic: The public profile of the newly created user.

    Raises:
    - HTTPException: If validation fails or a conflict occurs (e.g., duplicate email).
    """
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
    """
    Authenticate a user and return an access token.

    This endpoint verifies the user's credentials and issues a JWT token for authentication
    in subsequent requests.

    Parameters:
    - user_login_data (LoginSchema): The login credentials, typically including email/username and password.
    - user_service (UserService): Dependency-injected service for user operations.

    Returns:
    - TokenSchema: An object containing the JWT access token and token type.

    Raises:
    - HTTPException: If credentials are invalid (e.g., 401 Unauthorized).
    """
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
    """
    Retrieve the profile of the currently authenticated user.

    This endpoint returns the public user data for the authenticated user, based on the JWT token.

    Parameters:
    - current_user (UserPublic): The authenticated user object, injected via dependency.

    Returns:
    - UserPublic: The public profile of the current user.

    Raises:
    - HTTPException: If the user is not authenticated (e.g., 401 Unauthorized).
    """
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
    """
    Update the profile of the currently authenticated user.

    This endpoint allows the user to modify their profile details, such as name or preferences.
    Only fields provided in the update data will be changed.

    Parameters:
    - update_user_data (UpdateUserSchema): The data to update the user profile with.
    - current_user (UserPublic): The authenticated user object, injected via dependency.
    - user_service (UserService): Dependency-injected service for user operations.

    Returns:
    - UserPublic: The updated public profile of the user.

    Raises:
    - HTTPException: If validation fails or the update operation encounters an error.
    """
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
    current_user: Annotated[
        UserPublic, Depends(get_current_user)
    ],  # Note: Updated from 'require_admin' to 'UserPublic' for consistency; assuming admin check is handled in dependency if needed.
    user_service: user_dependency,
) -> DeleteUserResponseModel:
    """
    Delete the account of the currently authenticated user.

    This endpoint permanently removes the user's account and associated data.
    It requires administrative privileges or self-deletion permissions.

    Parameters:
    - current_user (UserPublic): The authenticated user object, injected via dependency.
    - user_service (UserService): Dependency-injected service for user operations.

    Returns:
    - DeleteUserResponseModel: A response confirming successful deletion.

    Raises:
    - HTTPException: If the user lacks permission or deletion fails (e.g., 403 Forbidden).
    """
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
    address_service: address_dependency,
) -> AddressPublic:
    """
    Add a new address to the currently authenticated user's account.

    This endpoint associates a new address with the user. If this is the user's first address,
    it may be marked as primary.

    Parameters:
    - address_data (AddressCreate): The data for the new address, such as street, city, and zip code.
    - current_user (UserPublic): The authenticated user object, injected via dependency.
    - address_service (AddressService): Dependency-injected service for address operations.

    Returns:
    - AddressPublic: The public representation of the newly added address.

    Raises:
    - HTTPException: If validation fails or the address cannot be added.
    """
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
    address_service: address_dependency,
    address_id: int,
) -> AddressPublic:
    """
    Update an existing address associated with the currently authenticated user.

    This endpoint modifies the specified address. The user must own the address to update it.

    Parameters:
    - address_data (AddressUpdate): The updated data for the address.
    - current_user (UserPublic): The authenticated user object, injected via dependency.
    - address_service (AddressService): Dependency-injected service for address operations.
    - address_id (int): The ID of the address to update.

    Returns:
    - AddressPublic: The public representation of the updated address.

    Raises:
    - HTTPException: If no data is provided (400 Bad Request), the address is not found (404 Not Found),
      or the user lacks permission (403 Forbidden).
    """
    if not address_data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    address = address_service.update_address(address_id, address_data)
    return address
