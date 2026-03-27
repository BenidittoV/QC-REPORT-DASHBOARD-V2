from sqlalchemy import select
from sqlalchemy.orm import Session

from app.legacy_seed import DEFAULT_ADMIN, LEGACY_TL_USERS
from app.models import User, UserRole
from app.security import hash_password


def seed_default_users(db: Session) -> None:
    admin = db.scalar(select(User).where(User.username == DEFAULT_ADMIN["username"]))
    if not admin:
        db.add(
            User(
                username=DEFAULT_ADMIN["username"],
                password_hash=hash_password(DEFAULT_ADMIN["password"]),
                role=UserRole.admin,
                tl_name=None,
            )
        )

    for item in LEGACY_TL_USERS:
        existing = db.scalar(select(User).where(User.username == item["username"]))
        if existing:
            continue
        db.add(
            User(
                username=item["username"],
                password_hash=hash_password(item["password"]),
                role=UserRole.tl,
                tl_name=item["tl_name"],
            )
        )

    db.commit()
