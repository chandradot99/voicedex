from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def client_ip(request: Request) -> str:
    """Rate-limit key. Behind Railway's proxy the socket peer is the proxy itself. Use the
    RIGHT-most X-Forwarded-For entry — the one our proxy appended. Left-most entries are
    client-supplied and could be forged to dodge the limit."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[-1].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=client_ip)
