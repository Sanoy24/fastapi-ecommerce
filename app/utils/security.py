from pwdlib import PasswordHash


# implement password hashing
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Hashes a plaintext password using the application's recommended scheme."""
    return password_hash.hash(password)


# implement password verification
def verify_password(plain_password: str, hash: str) -> bool:
    """Compare the hash password and the plaintext password for verification"""
    return password_hash.verify(password=plain_password, hash=hash)


# implement token generation

# token verification
