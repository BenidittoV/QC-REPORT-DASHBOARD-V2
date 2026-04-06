import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    tl = "tl"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, index=True)
    tl_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    uploaded_files: Mapped[list["DataFile"]] = relationship(
        "DataFile",
        back_populates="uploader",
        cascade="all, delete-orphan",
    )


class DataFile(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tl_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    agent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    uploader: Mapped[User] = relationship("User", back_populates="uploaded_files")
    records: Mapped[list["DataRecord"]] = relationship(
        "DataRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DataRecord(Base):
    __tablename__ = "file_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)

    call_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    call_datetime: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    duration_seconds: Mapped[float | None] = mapped_column(nullable=True)

    team_leader: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    call_result: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lov3_result: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sentiment_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sentiment_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_data_greetings_open: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_say_acc: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_agent_name: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_cust_name: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_unit_cust: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_kontrak_cust: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_choice_cust: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_greetings_close: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_say_benefit: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_do_simulasi: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_say_include_angsuran: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_say_segmentation_offer_range: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    raw_data_say_ref_contract_stat: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    file: Mapped[DataFile] = relationship("DataFile", back_populates="records")
