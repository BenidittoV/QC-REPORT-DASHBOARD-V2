from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import FileIngestStatus, FileSourceType, UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    ok: bool = True
    username: str
    role: UserRole
    tl_name: Optional[str] = None
    session_token: str


class ProcessRequest(BaseModel):
    mode: str = Field(default="TL")
    selected_tl: str | None = None
    selected_agent: str | None = None
    selected_month: str | None = None
    allowed_call_types: list[str] | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: UserRole = UserRole.tl
    tl_name: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    tl_name: Optional[str] = None
    role: Optional[UserRole] = None


class UserOut(BaseModel):
    id: int
    username: str
    role: UserRole
    tl_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FileUpdate(BaseModel):
    file_name: str


class FileOut(BaseModel):
    id: int
    file_name: str
    original_name: Optional[str] = None
    file_path: Optional[str] = None
    upload_date: datetime
    uploaded_by: int
    uploaded_by_username: Optional[str] = None
    source_type: FileSourceType
    is_active: bool

    ingest_status: FileIngestStatus
    ingest_error: Optional[str] = None
    processed_at: Optional[datetime] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    tl_count: Optional[int] = None
    agent_count: Optional[int] = None
    available_months: Optional[list[str]] = None

    class Config:
        from_attributes = True