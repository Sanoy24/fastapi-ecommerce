from pwdlib import PasswordHash
from datetime import timedelta, datetime, timezone
from typing import Dict, Optional, Any
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from app.core.config import settings
from app.schema.user_schema import TokenSchema

# implement password hashing
password_hash = PasswordHash.recommended()


class TokenError(Exception):
    """Custom exception for token-related errors."""


def hash_password(password: str) -> str:
    """Hashes a plaintext password using the application's recommended scheme."""
    return password_hash.hash(password)


# implement password verification
def verify_password(plain_password: str, hash: str) -> bool:
    """Compare the hash password and the plaintext password for verification"""
    return password_hash.verify(password=plain_password, hash=hash)


# implement token generation
def create_token(
    data: Dict[str, Any],
    expiration: Optional[timedelta] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """
    Create a JWT token with expiration and optional issuer/audience.

    Args:
        data: Payload data to encode.
        expiration: Optional timedelta for token lifetime; defaults to settings.JWT_DEFAULT_EXP_MINUTES.
        issuer: Optional issuer claim (iss).
        audience: Optional audience claim (aud).

    Returns:
        TokenSchema with the encoded token.
    """
    now = datetime.now(timezone.utc)
    if expiration is None:
        expiration = timedelta(minutes=settings.JWT_DEFAULT_EXP_MINUTES)

    expiration_time = now + expiration
    payload = {
        **data,
        "iat": int(now.timestamp()),  # Issued-at timestamp
        "exp": int(
            expiration_time.timestamp()
        ),  # Expiration timestamp (required as int)
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

    token = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return token


# token verification
def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT access token.

    Args:
        token: The JWT string to verify.

    Returns:
        Decoded payload as dict.

    Raises:
        TokenError: If token is invalid, expired, or malformed.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],  # List for security
            options={"verify_signature": True, "verify_exp": True},
        )
        return payload
    except ExpiredSignatureError:
        raise TokenError("Token has expired")
    except InvalidTokenError:
        raise TokenError("Invalid token")
    except jwt.DecodeError:  # Covers other decode issues
        raise TokenError("Malformed token")
