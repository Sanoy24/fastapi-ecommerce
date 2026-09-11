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
        "type": "access",
        **data,
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


def _decode_signed_token(token: str, expired_message: str, invalid_message: str, malformed_message: str) -> Dict[str, Any]:
    """
    Verify a JWT's signature and expiry and return its payload, without checking
    its 'type' claim. Callers must check 'type' themselves — see decode_access_token,
    decode_refresh_token, and decode_challenge_token, each of which allowlists the
    single type it accepts rather than denylisting the types it rejects.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_signature": True, "verify_exp": True},
        )
    except ExpiredSignatureError:
        raise TokenError(expired_message)
    except InvalidTokenError:
        raise TokenError(invalid_message)
    except jwt.DecodeError:
        raise TokenError(malformed_message)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.

    Args:
        token: The JWT string to verify.

    Returns:
        Decoded payload as dict.

    Raises:
        TokenError: If token is invalid, expired, malformed, or is not an access token.
    """
    payload = _decode_signed_token(token, "Token has expired", "Invalid token", "Malformed token")
    if payload.get("type") != "access":
        raise TokenError("Token is not a valid access token")
    return payload


def decode_refresh_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT refresh token.

    Args:
        token: The JWT refresh token string.

    Returns:
        Decoded payload as dict (contains 'sub', 'jti').

    Raises:
        TokenError: If the token is invalid, expired, or is not a refresh token.
    """
    payload = _decode_signed_token(
        token,
        "Refresh token has expired — please log in again",
        "Invalid refresh token",
        "Malformed refresh token",
    )
    if payload.get("type") != "refresh":
        raise TokenError("Access token cannot be used as a refresh token")
    return payload


def decode_challenge_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a short-lived MFA challenge token issued between password
    verification and second-factor verification.

    Args:
        token: The JWT challenge token string.

    Returns:
        Decoded payload as dict (contains 'sub').

    Raises:
        TokenError: If the token is invalid, expired, or is not an MFA challenge token.
    """
    payload = _decode_signed_token(
        token,
        "Challenge token has expired",
        "Invalid challenge token",
        "Malformed challenge token",
    )
    if payload.get("type") != "mfa_challenge":
        raise TokenError("Token is not a valid MFA challenge token")
    return payload

