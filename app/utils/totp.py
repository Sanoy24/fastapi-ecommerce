import pyotp

def generate_totp_secret() -> str:
    """Generate a new base32 secret for TOTP."""
    return pyotp.random_base32()

def generate_totp_uri(secret: str, email: str, issuer_name: str = "FastAPI E-commerce") -> str:
    """Generate the otpauth:// URI for the QR code."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer_name)

def verify_totp(secret: str, code: str) -> bool:
    """Verify a user-provided 6-digit code against their secret."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)
