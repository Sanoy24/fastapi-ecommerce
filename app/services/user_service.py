from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.redis import RedisClient
from app.crud.user import UserCrud
from app.models.user import User
from app.schema.user_schema import (
    ChangePasswordSchema,
    CreateUserSchema,
    LoginSchema,
    TokenSchema,
    UpdateUserSchema,
    UserPublic,
    MFASetupResponse,
    MFALoginChallenge,
)
from typing import Union
from app.utils.security import (
    TokenError,
    create_refresh_token,
    create_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

_RESET_TOKEN_TTL = 900  # 15 minutes in seconds
_REFRESH_TOKEN_PREFIX = "refresh:"
_RESET_TOKEN_PREFIX = "pwd_reset:"


class UserService:
    def __init__(self, db: Session, redis: RedisClient | None = None):
        """
        Initialize the UserService.

        Parameters:
        - db: SQLAlchemy database session.
        - redis: Optional RedisClient for token revocation and password-reset tokens.
                 When None, refresh token revocation and password reset are unavailable.
        """
        self.db = db
        self.crud = UserCrud(db=db)
        self.redis = redis

    def create_user(self, user_create_data: CreateUserSchema) -> User:
        """Create a new user; raises 400 if email already registered."""
        if self.crud.get_user_by_email(user_create_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        user = self.crud.create_user(user_create_data=user_create_data)
        import secrets
        user.verification_token = secrets.token_urlsafe(32)
        self.db.commit()
        self.db.refresh(user)
        return user

    def verify_email(self, token: str) -> None:
        """
        Verify a user's email address using their verification token.

        Raises:
            HTTPException 400 if the token is invalid.
        """
        user = self.crud.get_user_by_verification_token(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token",
            )
        user.is_verified = True
        user.verification_token = None
        self.db.commit()

    def authenticate_user(self, user_login_data: LoginSchema) -> User | None:
        """Return the User if credentials are valid, else None."""
        user = self.crud.get_user_by_email(email=user_login_data.email)
        if not user:
            return None
        if not verify_password(user_login_data.password, user.password_hash):
            return None
        return user

    def login(self, user_login_data: LoginSchema) -> Union[TokenSchema, MFALoginChallenge]:
        """
        Authenticate a user and issue access + refresh tokens or an MFA challenge.
        """
        user = self.authenticate_user(user_login_data=user_login_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
            )

        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified",
            )

        if user.mfa_enabled:
            # Issue a short-lived challenge token
            challenge_token = create_token(
                data={"sub": str(user.id), "type": "mfa_challenge"},
                expiration=timedelta(minutes=5),
            )
            return MFALoginChallenge(mfa_required=True, mfa_challenge_token=challenge_token)

        access_token = create_token(
            data={"sub": str(user.id)},
            expiration=timedelta(minutes=30),
        )
        refresh_token = create_refresh_token(user_id=user.id)
        return TokenSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=1800,  # 30 minutes in seconds
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenSchema:
        """
        Issue a new access token from a valid, non-revoked refresh token.

        Raises:
            HTTPException 401 if the refresh token is invalid, expired, or revoked.
        """
        try:
            payload = decode_refresh_token(refresh_token)
        except TokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            )

        jti = payload.get("jti")
        user_id = payload.get("sub")

        # Check revocation via Redis
        if self.redis is not None:
            revoked = await self.redis.client.get(f"{_REFRESH_TOKEN_PREFIX}{jti}")
            if revoked:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has been revoked. Please log in again.",
                )

        # Ensure user still exists
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        user = self.crud.get_user(user_id=int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        new_access_token = create_token(
            data={"sub": str(user.id)},
            expiration=timedelta(minutes=30),
        )
        new_refresh_token = create_refresh_token(user_id=user.id)

        # Refresh Token Rotation: Revoke the old token after issuing a new one
        if self.redis is not None:
            # calculate remaining TTL for the old token
            exp = payload.get("exp")
            if exp:
                import time
                ttl = int(exp) - int(time.time())
                if ttl > 0:
                    await self.redis.client.setex(
                        f"{_REFRESH_TOKEN_PREFIX}{jti}",
                        ttl,
                        "revoked"
                    )

        return TokenSchema(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="Bearer",
            expires_in=1800,
        )

    async def logout(self, refresh_token: str) -> None:
        """
        Revoke a refresh token by storing its JTI in Redis until expiry.

        Raises:
            HTTPException 400 if the token is already invalid.
        """
        try:
            payload = decode_refresh_token(refresh_token)
        except TokenError:
            # Token already invalid — no action needed
            return

        jti = payload.get("jti")
        exp = payload.get("exp")
        if self.redis is not None and jti and exp:
            import time
            ttl = max(int(exp - time.time()), 1)
            await self.redis.client.setex(f"{_REFRESH_TOKEN_PREFIX}{jti}", ttl, "1")

    def get_user_by_id(self, id: int) -> User:
        """Retrieve a user by ID; raises 404 if not found."""
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    def update_user(self, id: int, update_user_data: UpdateUserSchema) -> UserPublic:
        """Update user profile fields; raises 404 if user not found."""
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        for field, value in update_user_data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return UserPublic.model_validate(user)

    def change_password(self, user_id: int, data: ChangePasswordSchema) -> None:
        """
        Change the authenticated user's password.

        Raises:
            HTTPException 400 if current_password does not match.
            HTTPException 404 if user not found.
        """
        user = self.crud.get_user(user_id=user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        if not verify_password(data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        user.password_hash = hash_password(data.new_password)
        self.db.commit()

    async def forgot_password(self, email: str, arq_pool=None) -> None:
        """
        Initiate the password-reset flow.

        Always returns success (no email enumeration). Sends a reset email
        only when the email exists in the database.
        """
        import secrets

        user = self.crud.get_user_by_email(email=email)
        if not user:
            # Return silently to prevent email enumeration
            return

        token = secrets.token_urlsafe(32)
        if self.redis is not None:
            await self.redis.client.setex(
                f"{_RESET_TOKEN_PREFIX}{token}",
                _RESET_TOKEN_TTL,
                str(user.id),
            )

        if arq_pool:
            await arq_pool.enqueue_job("send_password_reset_email_task", email, token)
        else:
            # Fallback for sync or non-ARQ execution
            from app.services.email_service import send_password_reset_email
            await send_password_reset_email(to_address=email, reset_token=token)

    async def reset_password(self, token: str, new_password: str) -> None:
        """
        Complete the password-reset flow.

        Raises:
            HTTPException 400 if the token is invalid or expired.
            HTTPException 404 if the associated user no longer exists.
        """
        if self.redis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Password reset requires Redis. Please try again later.",
            )

        redis_key = f"{_RESET_TOKEN_PREFIX}{token}"
        user_id_str = await self.redis.client.get(redis_key)

        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired password-reset token",
            )

        user = self.crud.get_user(user_id=int(user_id_str))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        user.password_hash = hash_password(new_password)
        self.db.commit()

        # Invalidate the token so it cannot be reused
        await self.redis.client.delete(redis_key)

    def delete_user(self, id: int):
        """Delete a user by ID; raises 404 if not found."""
        user = self.crud.get_user(user_id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        self.db.delete(user)
        self.db.commit()

    def setup_mfa(self, user_id: int, email: str) -> MFASetupResponse:
        from app.utils.totp import generate_totp_secret, generate_totp_uri
        user = self.get_user_by_id(user_id)
        secret = generate_totp_secret()
        user.totp_secret = secret
        self.db.commit()
        uri = generate_totp_uri(secret, email)
        return MFASetupResponse(secret=secret, uri=uri)

    def enable_mfa(self, user_id: int, code: str) -> None:
        from app.utils.totp import verify_totp
        user = self.get_user_by_id(user_id)
        if not user.totp_secret:
            raise HTTPException(status_code=400, detail="MFA setup not initiated.")
        if not verify_totp(user.totp_secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code.")
        user.mfa_enabled = True
        self.db.commit()

    def disable_mfa(self, user_id: int, code: str) -> None:
        from app.utils.totp import verify_totp
        user = self.get_user_by_id(user_id)
        if not verify_totp(user.totp_secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code.")
        user.mfa_enabled = False
        user.totp_secret = None
        self.db.commit()

    def verify_mfa_login(self, challenge_token: str, code: str) -> TokenSchema:
        from app.utils.totp import verify_totp
        from app.utils import security
        try:
            payload = security.decode_access_token(challenge_token)
        except TokenError:
            raise HTTPException(status_code=401, detail="Invalid or expired challenge token.")

        if payload.get("type") != "mfa_challenge":
            raise HTTPException(status_code=401, detail="Invalid token type.")

        user_id = payload.get("sub")
        user = self.get_user_by_id(int(user_id))

        if not user.mfa_enabled or not user.totp_secret:
            raise HTTPException(status_code=400, detail="MFA is not enabled for this user.")

        if not verify_totp(user.totp_secret, code):
            raise HTTPException(status_code=401, detail="Invalid TOTP code.")

        access_token = create_token(
            data={"sub": str(user.id)},
            expiration=timedelta(minutes=30),
        )
        refresh_token = create_refresh_token(user_id=user.id)
        return TokenSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="Bearer",
            expires_in=1800,
        )

