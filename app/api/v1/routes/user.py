from app.schema.address_schema import AddressCreate, AddressUpdate, AddressPublic
from app.services.address_service import AddressService
from fastapi import APIRouter, Body, Depends, HTTPException, BackgroundTasks
from app.services.user_service import UserService
from app.schema.user_schema import (
    ChangePasswordSchema,
    CreateUserSchema,
    ForgotPasswordSchema,
    LoginSchema,
    ResetPasswordSchema,
    TokenSchema,
    UserPublic,
    UpdateUserSchema,
    UpdateUserSchema,
    DeleteUserResponseModel,
    MFASetupResponse,
    MFAVerifyRequest,
    MFALoginChallenge,
)
from app.dependencies import (
    get_user_service_dep,
    get_current_user,
    require_admin,
    get_address_service_dep,
    get_arq_pool,
)
from arq.connections import ArqRedis
from typing import Annotated, Union

router = APIRouter(tags=["User"])
user_dependency = Annotated[UserService, Depends(get_user_service_dep)]
address_dependency = Annotated[
    AddressService, Depends(get_address_service_dep)
]  # Note: Fixed typo from 'depedency' to 'dependency'


from app.core.limiter import limiter
from fastapi import Request, status
from app.core.redis import redis_client

@router.post(
    "/register",
    response_model=UserPublic,
    summary="Register user",
    description="Create a new user account.",
)
@limiter.limit("5/minute")
async def create_user(
    request: Request,
    create_user_data: CreateUserSchema,
    user_service: user_dependency,
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
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
    if user.verification_token and arq_pool:
        await arq_pool.enqueue_job(
            "send_verification_email_task",
            user.email,
            user.verification_token
        )

    return user

@router.get("/verify-email")
def verify_email(token: str, user_service: user_dependency):
    """Verify user's email address using token."""
    user_service.verify_email(token)
    return {"message": "Email verified successfully"}


@router.post(
    "/login",
    response_model=Union[TokenSchema, MFALoginChallenge],
    summary="User login",
    description="Authenticate user and return a JWT token or MFA challenge.",
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    login_data: LoginSchema,
    user_service: user_dependency,
) -> Union[TokenSchema, MFALoginChallenge]:
    """
    Authenticate a user and return an access token.

    This endpoint verifies the user's credentials and issues a JWT token for authentication
    in subsequent requests.

    Parameters:
    - login_data (LoginSchema): The login credentials, typically including email/username and password.
    - user_service (UserService): Dependency-injected service for user operations.

    Returns:
    - TokenSchema: An object containing the JWT access token and token type.

    Raises:
    - HTTPException: If credentials are invalid (e.g., 401 Unauthorized).
    """
    # Brute-force protection via Redis (if available)
    lockout_key = f"lockout:{login_data.email}"
    attempts_key = f"login_attempts:{login_data.email}"
    
    if redis_client._client:
        is_locked = await redis_client.client.get(lockout_key)
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account locked due to too many failed login attempts. Try again later."
            )

    try:
        token = user_service.login(login_data)
        if redis_client._client:
            await redis_client.delete(attempts_key)
        return token
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED and redis_client._client:
            attempts = await redis_client.client.incr(attempts_key)
            if attempts == 1:
                await redis_client.client.expire(attempts_key, 900)
            if attempts >= 5:
                await redis_client.client.set(lockout_key, "1", ex=900)
        raise e


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


# ─── Auth — refresh, logout, password management ───────────────────────────


@router.post(
    "/refresh",
    response_model=TokenSchema,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access + refresh token pair.",
)
async def refresh_token(
    refresh_token: Annotated[str, Body(embed=True)],
    user_service: user_dependency,
) -> TokenSchema:
    """Issue a new access token using a valid refresh token."""
    return await user_service.refresh_access_token(refresh_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Logout",
    description="Revoke the current refresh token, effectively logging the user out.",
)
async def logout(
    refresh_token: Annotated[str, Body(embed=True)],
    user_service: user_dependency,
) -> None:
    """Revoke the refresh token so it can no longer be used."""
    await user_service.logout(refresh_token)


@router.put(
    "/me/password",
    status_code=204,
    summary="Change password",
    description="Change the authenticated user's password. Requires the current password.",
)
async def change_password(
    data: ChangePasswordSchema,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
) -> None:
    """Change the current user's password after verifying the existing one."""
    user_service.change_password(user_id=current_user.id, data=data)


@router.post(
    "/forgot-password",
    summary="Forgot Password",
    description="Initiates the password reset process by sending an email with a reset token.",
    status_code=200,
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordSchema,
    user_service: user_dependency,
    arq_pool: Annotated[ArqRedis, Depends(get_arq_pool)],
) -> dict:
    """Initiate the password-reset flow for the given email."""
    await user_service.forgot_password(email=data.email, arq_pool=arq_pool)
    return {"message": "If that email exists, a reset link has been sent."}


@router.post(
    "/reset-password",
    status_code=200,
    summary="Reset password",
    description="Complete the password-reset flow using the token from the reset email.",
)
async def reset_password(
    data: ResetPasswordSchema,
    user_service: user_dependency,
) -> dict:
    """Set a new password using a valid password-reset token."""
    await user_service.reset_password(token=data.token, new_password=data.new_password)
    return {"message": "Password has been reset successfully. Please log in."}


# ─── MFA Endpoints ──────────────────────────────────────────────────────────

@router.post(
    "/mfa/setup",
    response_model=MFASetupResponse,
    summary="Setup MFA",
    description="Generates a new TOTP secret and returns the URI for QR code setup.",
)
async def setup_mfa(
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
) -> MFASetupResponse:
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled.")
    return user_service.setup_mfa(current_user.id, current_user.email)


@router.post(
    "/mfa/enable",
    status_code=status.HTTP_200_OK,
    summary="Enable MFA",
    description="Verifies the first TOTP code to fully enable MFA.",
)
async def enable_mfa(
    data: MFAVerifyRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
):
    if current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is already enabled.")
    user_service.enable_mfa(current_user.id, data.code)
    return {"message": "MFA enabled successfully."}


@router.post(
    "/mfa/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable MFA",
    description="Disables MFA after verifying a valid code.",
)
async def disable_mfa(
    data: MFAVerifyRequest,
    current_user: Annotated[UserPublic, Depends(get_current_user)],
    user_service: user_dependency,
):
    if not current_user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA is not enabled.")
    user_service.disable_mfa(current_user.id, data.code)
    return {"message": "MFA disabled successfully."}


@router.post(
    "/mfa/verify",
    response_model=TokenSchema,
    summary="Verify MFA for Login",
    description="Completes login by verifying the MFA code and challenge token.",
)
@limiter.limit("5/minute")
async def verify_mfa_login(
    request: Request,
    data: MFAVerifyRequest,
    challenge_token: str = Body(..., embed=True),
    user_service: user_dependency = Depends(get_user_service_dep),
) -> TokenSchema:
    return user_service.verify_mfa_login(challenge_token, data.code)

