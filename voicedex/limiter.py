from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from voicedex.config import settings


def client_ip(request: Request) -> str:
    """Rate-limit key. Behind Railway's proxy the socket peer is the proxy itself. Use the
    RIGHT-most X-Forwarded-For entry — the one our proxy appended. Left-most entries are
    client-supplied and could be forged to dodge the limit.

    With TRUST_CF_CONNECTING_IP, Cloudflare's CF-Connecting-IP (the visitor) is used instead; only
    enable it when the origin is reachable through Cloudflare alone, since the header is otherwise
    client-controlled."""
    if settings.trust_cf_connecting_ip:
        cf = request.headers.get("cf-connecting-ip")
        if cf:
            return cf.strip()
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
