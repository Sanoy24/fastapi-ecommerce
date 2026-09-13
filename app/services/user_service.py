from datetime import timedelta
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.redis import RedisClient
from app.crud.oauth_account import OAuthAccountCrud
from app.crud.user import UserCrud
from app.models.user import User
from app.schema.user_schema import (
    ChangePasswordSchema,
    CreateUserSchema,
    LinkedAccountResponse,
    LoginSchema,
    OAuthAuthorizationUrlResponse,
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
_OAUTH_STATE_PREFIX = "oauth_state:"
_OAUTH_STATE_TTL = 600  # 10 minutes — long enough for a provider consent screen


class UserService:
    def __init__(self, db: Session, redis: RedisClient | None = None):
        """
        Initialize the UserService.

        Parameters:
        - db: SQLAlchemy database session.
        - redis: Optional RedisClient for token revocation, password-reset tokens,
                 and OAuth state. When None, those flows are unavailable.
        """
        self.db = db
        self.crud = UserCrud(db=db)
        self.oauth_account_crud = OAuthAccountCrud(db=db)
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
        if not user or user.password_hash is None:
            # password_hash is None for an OAuth-only account (see
            # UserCrud.create_oauth_user) — there is no password to check.
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

        return self._issue_login_tokens(user)

    def _issue_login_tokens(self, user: User) -> Union[TokenSchema, MFALoginChallenge]:
        """Shared tail of every login path (password and OAuth): an MFA
        challenge if the account has it enabled, otherwise a real token
        pair. Kept in one place so OAuth login can't accidentally skip the
        MFA check a password login enforces."""
        if user.mfa_enabled:
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
        if user.password_hash is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account has no password yet — use set-password instead",
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
        if not user.totp_secret:
            raise HTTPException(status_code=400, detail="MFA is not enabled for this user.")
        if not verify_totp(user.totp_secret, code):
            raise HTTPException(status_code=400, detail="Invalid TOTP code.")
        user.mfa_enabled = False
        user.totp_secret = None
        self.db.commit()

    def verify_mfa_login(self, challenge_token: str, code: str) -> TokenSchema:
        from app.utils.totp import verify_totp
        from app.utils import security
        try:
            payload = security.decode_challenge_token(challenge_token)
        except TokenError:
            raise HTTPException(status_code=401, detail="Invalid or expired challenge token.")

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload.")
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

    def set_initial_password(self, user_id: int, new_password: str) -> None:
        """For an OAuth-only account (password_hash is NULL) to gain a
        password-based login option. Distinct from change_password, which
        requires proving a password that doesn't exist yet — this is the
        endpoint unlink_oauth_account tells such a user to use before it
        will let them remove their only sign-in method."""
        user = self.get_user_by_id(user_id)
        if user.password_hash is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password already set — use change-password instead",
            )
        user.password_hash = hash_password(new_password)
        self.db.commit()

    # ─── OAuth (social login) ───────────────────────────────────────────

    async def get_oauth_authorization_url(self, provider: str) -> OAuthAuthorizationUrlResponse:
        import secrets

        from app.services import oauth_provider

        oauth_provider.require_supported_provider(provider)
        state = secrets.token_urlsafe(24)
        if self.redis is not None:
            await self.redis.client.setex(f"{_OAUTH_STATE_PREFIX}{state}", _OAUTH_STATE_TTL, provider)
        url = oauth_provider.build_authorization_url(provider, state)
        return OAuthAuthorizationUrlResponse(authorization_url=url, state=state)

    async def _consume_oauth_state(self, provider: str, state: str) -> None:
        """One-time-use CSRF check: the state this provider redirect carries
        back must match one we handed out for this exact provider and not
        have been used already."""
        if self.redis is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OAuth login requires Redis. Please try again later.",
            )
        key = f"{_OAUTH_STATE_PREFIX}{state}"
        stored_provider = await self.redis.client.get(key)
        if not stored_provider or stored_provider != provider:
            raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
        await self.redis.client.delete(key)

    async def oauth_login(self, provider: str, code: str, state: str) -> Union[TokenSchema, MFALoginChallenge]:
        """Log in or sign up via an OAuth provider.

        An existing link (provider, provider_user_id) always wins — that
        identity has already proven itself once. Failing that, an email
        match against an existing password account only auto-links when
        the provider itself vouches the email is verified; otherwise
        someone could take over an existing account just by registering an
        OAuth identity under the victim's (unverified, provider-side)
        email address. A brand-new signup has the same requirement, for
        the same reason applied to account creation instead of takeover.
        """
        from app.services import oauth_provider

        await self._consume_oauth_state(provider, state)
        profile = await oauth_provider.exchange_code_and_fetch_profile(provider, code)

        existing_link = self.oauth_account_crud.get_by_provider_identity(provider, profile.provider_user_id)
        if existing_link:
            return self._issue_login_tokens(existing_link.user)

        user = self.crud.get_user_by_email(profile.email)
        if user:
            if not profile.email_verified:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"An account with this email already exists. Log in with your "
                        f"password, then link {provider} from your account settings."
                    ),
                )
            self.oauth_account_crud.create(user.id, provider, profile.provider_user_id, profile.email)
            return self._issue_login_tokens(user)

        if not profile.email_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Your {provider} email must be verified to sign up this way",
            )

        first_name, _, last_name = (profile.name or "").partition(" ")
        user = self.crud.create_oauth_user(profile.email, first_name or None, last_name or None)
        self.oauth_account_crud.create(user.id, provider, profile.provider_user_id, profile.email)
        return self._issue_login_tokens(user)

    async def link_oauth_account(
        self, user_id: int, provider: str, code: str, state: str
    ) -> LinkedAccountResponse:
        """Attach a new provider to an already-authenticated account. No
        email-verification requirement here (unlike oauth_login) — the
        user is already proven to own the target account by their session,
        so this is a "connect" action they're explicitly taking, not an
        identity claim that needs independent verification."""
        from app.services import oauth_provider

        await self._consume_oauth_state(provider, state)
        profile = await oauth_provider.exchange_code_and_fetch_profile(provider, code)

        existing_link = self.oauth_account_crud.get_by_provider_identity(provider, profile.provider_user_id)
        if existing_link:
            if existing_link.user_id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"This {provider} account is already linked to another user",
                )
            return LinkedAccountResponse.model_validate(existing_link)

        if self.oauth_account_crud.get_for_user_and_provider(user_id, provider):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have a {provider} account linked — unlink it first",
            )

        account = self.oauth_account_crud.create(user_id, provider, profile.provider_user_id, profile.email)
        return LinkedAccountResponse.model_validate(account)

    def unlink_oauth_account(self, user_id: int, provider: str) -> None:
        account = self.oauth_account_crud.get_for_user_and_provider(user_id, provider)
        if not account:
            raise HTTPException(status_code=404, detail=f"No linked {provider} account found")

        user = self.get_user_by_id(user_id)
        remaining_links = self.oauth_account_crud.list_for_user(user_id)
        if user.password_hash is None and len(remaining_links) <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unlink your only sign-in method — set a password first",
            )
        self.oauth_account_crud.delete(account)

    def list_linked_accounts(self, user_id: int) -> List[LinkedAccountResponse]:
        return [
            LinkedAccountResponse.model_validate(a)
            for a in self.oauth_account_crud.list_for_user(user_id)
        ]

