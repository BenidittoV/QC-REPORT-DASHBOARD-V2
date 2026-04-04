import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    tl = "tl"


class FileSourceType(str, enum.Enum):
    admin = "admin"
    tl_manual = "tl_manual"


class FileIngestStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    tl_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    uploaded_files: Mapped[list["ExcelFile"]] = relationship(
        "ExcelFile",
        back_populates="uploader",
        cascade="all, delete-orphan",
    )


class ExcelFile(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Tetap disimpan untuk local/dev atau audit ringan.
    # Di production Koyeb, jangan dijadikan source of truth.
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[FileSourceType] = mapped_column(Enum(FileSourceType), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ingest_status: Mapped[FileIngestStatus] = mapped_column(
        Enum(FileIngestStatus),
        default=FileIngestStatus.pending,
        nullable=False,
        index=True,
    )
    ingest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tl_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    meta_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    available_months_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    uploader: Mapped[User] = relationship("User", back_populates="uploaded_files")

    records: Mapped[list["CallRecord"]] = relationship(
        "CallRecord",
        back_populates="file",
        cascade="all, delete-orphan",
    )


class CallRecord(Base):
    __tablename__ = "call_records"
    __table_args__ = (
        UniqueConstraint("file_id", "row_number", name="uq_call_records_file_row_number"),
        Index("ix_call_records_file_tl_agent_month", "file_id", "tl_name", "agent_name", "month_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    tl_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    agent_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    call_result: Mapped[str | None] = mapped_column(String(255), nullable=True)
    call_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    month_key: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)

    # Menyimpan row hasil ingest agar analytics lama tetap bisa dipakai
    # tanpa parse ulang Excel.
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    file: Mapped[ExcelFile] = relationship("ExcelFile", back_populates="records")