from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Gate every request behind a shared key, but only if one is configured.

    Leaving API_KEY blank in the environment turns auth off, which keeps local
    development and the test suite simple. Set it in production.
    """
    expected = get_settings().api_key
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
