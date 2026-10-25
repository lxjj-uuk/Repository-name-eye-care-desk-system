import secrets

from fastapi import APIRouter, HTTPException, status

from ..config import settings
from ..schemas import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    username_ok = secrets.compare_digest(body.username, settings.demo_username)
    password_ok = secrets.compare_digest(body.password, settings.demo_password)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    return TokenResponse(access_token=settings.api_token)
