from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.database import SessionLocal
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas import LoginRequest, LoginResponse
from app.security import create_session_token, verify_password
from app.services.file_service import list_available_files_for_user

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.username == payload.username.strip()))
        if not user:
            raise HTTPException(status_code=401, detail="Username atau password salah.")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Username atau password salah.")
        token = create_session_token(user_id=user.id, username=user.username, role=user.role.value)
        available_files = list_available_files_for_user(db) if user.role == UserRole.tl else []
        return LoginResponse(
            username=user.username,
            role=user.role,
            tl_name=user.tl_name,
            session_token=token,
            available_files=available_files,
        )
    finally:
        db.close()


@router.post("/logout")
def logout():
    return {"ok": True}


@router.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "tl_name": user.tl_name,
    }
