from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from passlib.context import CryptContext

from app.config import settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.secret_key, salt="qc-dashboard-session")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_session_token(*, user_id: int, username: str, role: str) -> str:
    return serializer.dumps({
        "user_id": user_id,
        "username": username,
        "role": role,
    })


def decode_session_token(token: str) -> dict:
    return serializer.loads(token, max_age=settings.session_max_age_seconds)
