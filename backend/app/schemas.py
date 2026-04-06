from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models import UserRole


class FileListItem(BaseModel):
    id: int
    file_name: str
    original_name: Optional[str] = None
    upload_date: datetime
    uploaded_by: int
    uploaded_by_username: Optional[str] = None
    is_active: bool
    row_count: int = 0
    tl_count: int = 0
    agent_count: int = 0
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    ok: bool = True
    username: str
    role: UserRole
    tl_name: Optional[str] = None
    session_token: str
    available_files: list[FileListItem] = Field(default_factory=list)


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


class FileUpdate(BaseModel):
    file_name: str
