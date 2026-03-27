from typing import Generator, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import BadSignature, SignatureExpired, decode_session_token


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    x_session_token: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Token sesi tidak ada.")
    try:
        payload = decode_session_token(x_session_token)
    except SignatureExpired as exc:
        raise HTTPException(status_code=401, detail="Sesi login sudah kedaluwarsa.") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Token sesi tidak valid.") from exc

    user = db.get(User, payload.get("user_id"))
    if not user:
        raise HTTPException(status_code=401, detail="User sesi tidak ditemukan.")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Hanya admin yang boleh mengakses endpoint ini.")
    return user
