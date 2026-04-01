"""Single-role authentication — hardcoded credentials via env vars."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jose import jwt, JWTError

from config import app_settings

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def _create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=app_settings.JWT_EXPIRE_HOURS)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, app_settings.JWT_SECRET, algorithm=app_settings.JWT_ALGORITHM)


def _verify_token(token: str) -> str | None:
    """Returns email if valid, None if not."""
    try:
        payload = jwt.decode(token, app_settings.JWT_SECRET, algorithms=[app_settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


@router.post("/login")
def login(req: LoginRequest):
    if not app_settings.JWT_SECRET or not app_settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="Auth not configured — set JWT_SECRET and ADMIN_PASSWORD env vars")

    if req.email != app_settings.ADMIN_EMAIL or req.password != app_settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _create_token(req.email)
    return TokenResponse(access_token=token)


@router.get("/me")
def get_me(authorization: str = ""):
    """Validate token and return user info."""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    email = _verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"email": email, "role": "admin"}
