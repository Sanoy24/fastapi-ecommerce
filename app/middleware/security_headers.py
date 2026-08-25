from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Prevent browsers from performing MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking by denying rendering in a frame
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enforce HTTPS connections (HSTS) - set to 1 year
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        # Control resources the user agent is allowed to load
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response
