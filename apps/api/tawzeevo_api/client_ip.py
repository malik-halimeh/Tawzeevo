"""Client IP resolution for abuse controls (login/recovery throttles, public rate limits).

Behind a reverse proxy the socket peer is the proxy, so keying limits on it either puts every
visitor in one bucket or, if forwarded headers are trusted blindly, lets a caller choose its own
key. The rule here is the trusted-hop-count rule: with `TRUSTED_PROXY_HOPS = n` the client is the
n-th address from the right of `X-Forwarded-For`, because each trusted proxy appends the peer it
saw and nothing a caller puts in the header can move that position. With `0` (the default, direct
exposure or a local development server) the socket peer is used and the header is ignored.
"""

from __future__ import annotations

from collections.abc import Iterable

UNKNOWN = "unknown"


def resolve_client_ip(peer: str | None, forwarded_for: str | None, trusted_proxy_hops: int) -> str:
    """Pure resolution rule; `forwarded_for` is the raw X-Forwarded-For header value."""
    if trusted_proxy_hops <= 0:
        return peer or UNKNOWN
    chain = [part.strip() for part in (forwarded_for or "").split(",") if part.strip()]
    if len(chain) < trusted_proxy_hops:
        # Fewer hops than configured: the request did not come through the expected proxies
        # (or the proxy did not set the header). Fall back to the peer rather than trusting
        # whatever is left of the header.
        return peer or UNKNOWN
    return chain[-trusted_proxy_hops]


def header_value(headers: Iterable[tuple[bytes, bytes]], name: bytes) -> str | None:
    """First matching raw ASGI header (lower-case name), decoded."""
    for key, value in headers:
        if key.lower() == name:
            return value.decode("latin-1")
    return None
