"""Authentication and user management."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import app_settings
from database import get_db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AddUserRequest(BaseModel):
    email: str
    password: str
    role: str = "viewer"


class ChangePasswordRequest(BaseModel):
    password: str


def _create_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=app_settings.JWT_EXPIRE_HOURS)
    payload = {"sub": email, "exp": expire}
    return jwt.encode(payload, app_settings.JWT_SECRET, algorithm=app_settings.JWT_ALGORITHM)


def _verify_token(token: str) -> Optional[str]:
    """Returns email if valid, None if not."""
    try:
        payload = jwt.decode(token, app_settings.JWT_SECRET, algorithms=[app_settings.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def _require_auth(authorization: str = Header("")) -> str:
    """Dependency that extracts and validates JWT, returns email."""
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    email = _verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return email


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    if not app_settings.JWT_SECRET:
        raise HTTPException(status_code=500, detail="Auth not configured — set JWT_SECRET env var")

    # Check database users first
    row = db.execute(
        text("SELECT password_hash FROM app_users WHERE email = :email"),
        {"email": req.email},
    ).first()

    if row and pwd_context.verify(req.password, row[0]):
        return TokenResponse(access_token=_create_token(req.email))

    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/me")
def get_me(email: str = Depends(_require_auth)):
    return {"email": email, "role": "admin"}


# ── User Management ──────────────────────────────────────────────

@router.get("/users")
def list_users(email: str = Depends(_require_auth), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT id, email, role, created_at FROM app_users ORDER BY created_at"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.post("/users")
def add_user(req: AddUserRequest, email: str = Depends(_require_auth), db: Session = Depends(get_db)):
    # Check if email already exists
    exists = db.execute(
        text("SELECT 1 FROM app_users WHERE email = :email"),
        {"email": req.email},
    ).first()
    if exists:
        raise HTTPException(status_code=409, detail="User already exists")

    hashed = pwd_context.hash(req.password)
    db.execute(text(
        "INSERT INTO app_users (email, password_hash, role) VALUES (:email, :hash, :role)"
    ), {"email": req.email, "hash": hashed, "role": req.role})
    db.commit()
    return {"ok": True, "email": req.email}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, email: str = Depends(_require_auth), db: Session = Depends(get_db)):
    # Don't allow deleting yourself
    row = db.execute(
        text("SELECT email FROM app_users WHERE id = :id"),
        {"id": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if row[0] == email:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db.execute(text("DELETE FROM app_users WHERE id = :id"), {"id": user_id})
    db.commit()
    return {"ok": True}


@router.patch("/users/{user_id}/password")
def change_password(user_id: int, req: ChangePasswordRequest, email: str = Depends(_require_auth), db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT 1 FROM app_users WHERE id = :id"),
        {"id": user_id},
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    hashed = pwd_context.hash(req.password)
    db.execute(text(
        "UPDATE app_users SET password_hash = :hash WHERE id = :id"
    ), {"hash": hashed, "id": user_id})
    db.commit()
    return {"ok": True}
