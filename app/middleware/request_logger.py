import json
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from starlette.types import ASGIApp, Receive, Scope, Send, Message
from app.core.logger import logger


SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}
MAX_BODY_LOG_BYTES = 1024 * 16  # 16 KB - cap how much of the body we log
SENSITIVE_BODY_KEYS = {"password", "token", "access_token", "refresh_token"}

# Paths to exclude from logging
EXCLUDED_PATHS = {"/api/v1/openapi.json", "/docs", "/redoc", "/metrics"}


def _safe_json_loads(b: bytes) -> Any:
    try:
        return json.loads(b.decode("utf-8"))
    except Exception:
        try:
            return b.decode("utf-8", errors="replace")
        except Exception:
            return "<binary data>"


def _redact_body(data: Any) -> Any:
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            if k.lower() in SENSITIVE_BODY_KEYS:
                redacted[k] = "<redacted>"
            else:
                redacted[k] = _redact_body(v)
        return redacted

    elif isinstance(data, list):
        return [_redact_body(item) for item in data]

    return data  # primitives unchanged


def _redact_headers(headers: Dict[str, str]) -> Dict[str, Optional[str]]:
    redacted = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            redacted[k] = "<redacted>"
        else:
            redacted[k] = v
    return redacted


class LoggingMiddleware:
    """
    ASGI middleware that safely logs requests and responses without
    preventing downstream access to bodies.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            # Non-HTTP (websocket, etc.) — pass through
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in EXCLUDED_PATHS:
            # Skip logging for excluded paths
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        start = time.time()

        # --- Read and buffer the entire request body from receive ---
        body_chunks = []
        more_body = True
        # We will consume the incoming receive until no more_body
        while more_body:
            message = await receive()
            if message["type"] != "http.request":
                # Unexpected message, but forward it
                body_chunks.append(b"")
                more_body = False
                break
            chunk = message.get("body", b"")
            if chunk:
                body_chunks.append(chunk)
            more_body = message.get("more_body", False)
        request_body_bytes = b"".join(body_chunks)

        # Build a new receive function that replays the buffered body for downstream
        async def receive_replay() -> Message:
            nonlocal request_body_bytes
            # send the full body once, with more_body False
            msg = {
                "type": "http.request",
                "body": request_body_bytes,
                "more_body": False,
            }

            # After first call, future calls should return empty body messages
            async def _empty() -> Message:
                return {"type": "http.request", "body": b"", "more_body": False}

            # replace function so multiple calls are safe
            nonlocal receive_replay
            receive_replay = _empty  # type: ignore
            return msg

        # gather request metadata
        headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
        request_info = {
            "request_id": request_id,
            "method": scope.get("method"),
            "path": scope.get("path"),
            "raw_path": (
                scope.get("raw_path").decode("latin-1")
                if scope.get("raw_path")
                else None
            ),
            "query_string": scope.get("query_string", b"").decode(
                "utf-8", errors="replace"
            ),
            "client": (
                f"{scope.get('client')[0]}:{scope.get('client')[1]}"
                if scope.get("client")
                else None
            ),
            "headers": _redact_headers(headers),
        }

        # parse/log request body with cap & redaction
        if request_body_bytes:
            if len(request_body_bytes) > MAX_BODY_LOG_BYTES:
                truncated = request_body_bytes[:MAX_BODY_LOG_BYTES]
                parsed = _safe_json_loads(truncated)
                redacted = _redact_body(parsed)
                request_info["body"] = {
                    "truncated": True,
                    "preview": redacted,
                    "full_size": len(request_body_bytes),
                }
            else:
                parsed = _safe_json_loads(request_body_bytes)
                request_info["body"] = _redact_body(parsed)
        else:
            request_info["body"] = None

        try:
            logger.info(f"Request: {json.dumps(request_info, default=str)}")
        except Exception:
            logger.info("Request: (could not serialize request info)")

        # --- Intercept send to capture response ---
        response_status = None
        response_headers_bytes = []
        response_body_accum = bytearray()
        response_body_size = 0
        response_logged = {}

        async def send_wrapper(message: Message) -> None:
            nonlocal \
                response_status, \
                response_headers_bytes, \
                response_body_accum, \
                response_body_size, \
                response_logged

            if message["type"] == "http.response.start":
                response_status = message.get("status")
                response_headers_bytes = message.get("headers", [])
                # forward immediately
                await send(message)
                return

            if message["type"] == "http.response.body":
                chunk = message.get("body", b"")
                more_body = message.get("more_body", False)

                # accumulate for logging up to the cap
                if chunk:
                    remaining_cap = MAX_BODY_LOG_BYTES - response_body_size
                    if remaining_cap > 0:
                        to_store = chunk[:remaining_cap]
                        response_body_accum.extend(to_store)
                        response_body_size += len(to_store)

                # forward the chunk unchanged to the client
                await send(message)

                # If this is the final chunk, prepare log
                if not more_body:
                    # convert headers to dict (decode)
                    headers = {
                        k.decode(): v.decode() for k, v in response_headers_bytes
                    }
                    response_logged = {
                        "request_id": request_id,
                        "status_code": response_status,
                        "headers": _redact_headers(headers),
                        "process_time_seconds": f"{time.time() - start:.4f}",
                    }

                    if response_body_size == 0:
                        response_logged["body"] = None
                    else:
                        # try parse JSON, else show text preview
                        parsed_body = _safe_json_loads(bytes(response_body_accum))
                        response_logged["body"] = _redact_body(parsed_body)

                    # if the full response was larger than cap, include a hint
                    # Note: we don't know full response size without buffering everything: we only know preview size
                    if response_body_size >= MAX_BODY_LOG_BYTES:
                        response_logged["body_truncated"] = True

                    try:
                        logger.info(
                            f"Response: {json.dumps(response_logged, default=str)}"
                        )
                    except Exception:
                        logger.info("Response: (could not serialize response info)")

                return

            # unexpected message types forwarded
            await send(message)

        # Call the next app with the replaying receive and send_wrapper
        await self.app(scope, receive_replay, send_wrapper)
