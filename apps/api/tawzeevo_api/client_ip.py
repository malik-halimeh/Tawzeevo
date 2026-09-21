"""Client IP resolution for abuse controls (login/recovery throttles, public rate limits).

Behind a reverse proxy the socket peer is the proxy, so keying limits on it either puts every
visitor in one bucket or, if forwarded headers are trusted blindly, lets a caller choose its own
key. The rule here is the trusted-hop-count rule: with `TRUSTED_PROXY_HOPS = n` the client is the
n-th address from the right of `X-Forwarded-For`, because each trusted proxy appends the peer it
saw and nothing a caller puts in the header can move that position. With `0` (the default, direct
exposure or a local development server) forwarded client-IP headers are ignored entirely and the
socket peer is used.

Configure `n` as the real number of proxies that append to `X-Forwarded-For`, and **never
higher**. Over-configuration is the dangerous direction: with `n = 2` behind a single proxy the
selected position falls on text the caller itself supplied (a request sent with
`X-Forwarded-For: 203.0.113.9` arrives as `203.0.113.9, <client>`), so the caller picks its own
throttle bucket — exactly the abuse this rule exists to prevent. Under-configuration is the safe
failure mode: it can put several visitors in one shared bucket (a stricter limit for them), but it
never lets a caller choose its key. When the hop count is uncertain, take the lower value.
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
