"""Fixed public paths, bounded rate limiting, privacy headers, and log redaction."""

import logging
import re
from hashlib import sha256
from threading import Lock
from time import monotonic

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PRIVACY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
}
CATALOG_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
_TOKEN_LOG_PATTERN = re.compile(r"[a-fA-F0-9]{32}(?:\.|%2[eE])[A-Za-z0-9_-]{43}")
_OAUTH_LOG_PATTERN = re.compile(r"(?i)\b(code|state|refresh_token|access_token)=[^&\s\"']+")


class CapabilityLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = _TOKEN_LOG_PATTERN.sub("[invoice-link-redacted]", record.getMessage())
        record.msg = _OAUTH_LOG_PATTERN.sub(r"\1=[redacted]", message)
        record.args = ()
        return True


def install_capability_log_redaction() -> None:
    for name in ("uvicorn.access", "uvicorn.error", "tawzeevo.public_invoices"):
        logger = logging.getLogger(name)
        if not any(isinstance(item, CapabilityLogFilter) for item in logger.filters):
            logger.addFilter(CapabilityLogFilter())


class PublicInvoiceRateLimiter:
    """Per-process sliding window; fail closed when the bounded client map is full."""

    def __init__(self, limit: int = 60, window: int = 60, max_clients: int = 4096) -> None:
        self.limit = limit
        self.window = window
        self.max_clients = max_clients
        self._clients: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, client: str) -> bool:
        now = monotonic()
        key = sha256(client.encode()).hexdigest()
        with self._lock:
            self._clients = {
                k: [t for t in times if t > now - self.window]
                for k, times in self._clients.items()
                if times[-1] > now - self.window
            }
            if key not in self._clients and len(self._clients) >= self.max_clients:
                return False
            times = self._clients.setdefault(key, [])
            if len(times) >= self.limit:
                return False
            times.append(now)
            return True


class PublicInvoicePrivacyMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.limiter = PublicInvoiceRateLimiter()
        # Storefront catalog pages are shareable and image-heavy: a wider, separate budget.
        self.catalog_limiter = PublicInvoiceRateLimiter(limit=600, window=60)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        public = path.startswith("/api/v1/public/")
        # Private customer links (/api/v1/public/invoice...) get no-store/noindex headers; the
        # per-business storefront catalog is public and cacheable by design (PHASE_05.md C).
        private_public = public and path.startswith("/api/v1/public/invoice")
        private_link = path.startswith("/api/v1/invoices/") and "/capabilities" in path
        if scope["type"] != "http" or not (public or private_link):
            await self.app(scope, receive, send)
            return

        started = False
        headers = PRIVACY_HEADERS if (private_public or private_link) else CATALOG_HEADERS

        async def private_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                existing = [
                    (k, v)
                    for k, v in message.get("headers", [])
                    if k.decode().lower() not in {s.lower() for s in headers}
                ]
                message["headers"] = existing + [
                    (k.lower().encode(), v.encode()) for k, v in headers.items()
                ]
            await send(message)

        client = scope.get("client")
        limiter = self.limiter if private_public else self.catalog_limiter
        if public and not limiter.allow(client[0] if client else "unknown"):
            await JSONResponse(
                {"detail": {"code": "RATE_LIMITED", "message": "Please try again later"}},
                status_code=429,
                headers={"Retry-After": "60"},
            )(scope, receive, private_send)
            return
        try:
            await self.app(scope, receive, private_send)
        except Exception:
            if not private_public or started:
                raise
            # Do not log request headers or exception objects that could contain a secret.
            logging.getLogger("tawzeevo.public_invoices").error("Public invoice request failed")
            await JSONResponse(
                {
                    "detail": {
                        "code": "PUBLIC_INVOICE_UNAVAILABLE",
                        "message": "Invoice is temporarily unavailable",
                    }
                },
                status_code=503,
            )(scope, receive, private_send)
