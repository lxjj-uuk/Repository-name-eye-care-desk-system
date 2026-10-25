import secrets
from typing import Optional

from fastapi import Header, HTTPException, status

from .config import settings


def require_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    token = authorization.split(" ", 1)[1].strip()
    if not secrets.compare_digest(token, settings.api_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        )
    return token
