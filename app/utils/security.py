from pwdlib import PasswordHash
from datetime import timedelta, datetime, timezone
from typing import Dict, Optional, Any
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from app.core.config import settings

# implement password hashing
password_hash = PasswordHash.recommended()


class TokenError(Exception):
    """Custom exception for token-related errors."""


def hash_password(password: str) -> str:
    """Hashes a plaintext password using the application's recommended scheme."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hash: str) -> bool:
    """Compare the hash password and the plaintext password for verification"""
    return password_hash.verify(password=plain_password, hash=hash)


def create_token(
    data: Dict[str, Any],
    expiration: Optional[timedelta] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """
    Create a JWT access token with expiration and optional issuer/audience.

    Args:
        data: Payload data to encode.
        expiration: Optional timedelta for token lifetime; defaults to settings.JWT_DEFAULT_EXP_MINUTES.
        issuer: Optional issuer claim (iss).
        audience: Optional audience claim (aud).

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    if expiration is None:
        expiration = timedelta(minutes=settings.JWT_DEFAULT_EXP_MINUTES)

    expiration_time = now + expiration
    payload = {
        **data,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expiration_time.timestamp()),
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token


def create_refresh_token(user_id: int) -> str:
    """
    Create a long-lived JWT refresh token.

    The token carries a 'type': 'refresh' claim so it cannot be used as an
    access token.  Actual revocation is enforced by the service layer, which
    stores the token JTI in Redis with a matching TTL.

    Args:
        user_id: The user's integer primary key.

    Returns:
        Encoded JWT refresh token string.
    """
    import uuid

    now = datetime.now(timezone.utc)
    expiration = timedelta(days=settings.JWT_REFRESH_EXP_DAYS)
    expiration_time = now + expiration
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),  # Unique ID — used for revocation
        "iat": int(now.timestamp()),
        "exp": int(expiration_time.timestamp()),
    }
    return jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.

    Args:
        token: The JWT string to verify.

    Returns:
        Decoded payload as dict.

    Raises:
        TokenError: If token is invalid, expired, malformed, or is a refresh token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
        if payload.get("type") == "refresh":
            raise TokenError("Refresh token cannot be used as an access token")
        return payload
    except ExpiredSignatureError:
        raise TokenError("Token has expired")
    except InvalidTokenError:
        raise TokenError("Invalid token")
    except jwt.DecodeError:
        raise TokenError("Malformed token")


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT refresh token.

    Args:
        token: The JWT refresh token string.

    Returns:
        Decoded payload as dict (contains 'sub', 'jti').

    Raises:
        TokenError: If the token is invalid, expired, or is an access token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
        if payload.get("type") != "refresh":
            raise TokenError("Access token cannot be used as a refresh token")
        return payload
    except ExpiredSignatureError:
        raise TokenError("Refresh token has expired — please log in again")
    except InvalidTokenError:
        raise TokenError("Invalid refresh token")
    except jwt.DecodeError:
        raise TokenError("Malformed refresh token")

