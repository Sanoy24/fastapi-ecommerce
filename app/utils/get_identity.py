from fastapi import Request


def get_identity(request: Request):
    user_id = request.state.user_id if hasattr(request.state, "user_id") else None
    session_id = (
        request.state.session_id if hasattr(request.state, "session_id") else None
    )
