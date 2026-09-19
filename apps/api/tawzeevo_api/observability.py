"""Request correlation and a structured access log (PHASE_09.md G, P9-M3).

Every response carries `X-Request-ID` (the caller's, when it is a safe token, otherwise a fresh
one). One JSON line per request goes to the `tawzeevo.access` logger: method, route template
(never the raw path with its ids), status, duration, request id, client. Query strings, bodies,
headers and secrets are never logged; the capability redaction filter still applies on top."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

access_logger = logging.getLogger("tawzeevo.access")
request_id_var: ContextVar[str] = ContextVar("tawzeevo_request_id", default="-")
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# Paths that are noise in the access log (health probes from the platform).
_QUIET = frozenset({"/health", "/health/database"})


def current_request_id() -> str:
    return request_id_var.get()


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = next(
            (v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"x-request-id"),
            "",
        )
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
            path = scope.get("path", "")
            if path not in _QUIET:
                route = scope.get("route")
                template = getattr(route, "path", None) or "unmatched"
                client = scope.get("client")
                access_logger.info(
                    json.dumps(
                        {
                            "request_id": request_id,
                            "method": scope.get("method", ""),
                            "route": template,
                            "status": status_code,
                            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                            "client": client[0] if client else None,
                        },
                        separators=(",", ":"),
                    )
                )
