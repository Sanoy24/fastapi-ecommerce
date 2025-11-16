import uuid


def generate_session_id() -> str:
    """Generate a secure anonymous session ID"""
    return str(uuid.uuid4())
