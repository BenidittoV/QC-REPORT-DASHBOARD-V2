import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ExcelFile, FileSourceType, User


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def ensure_storage_dirs() -> None:
    Path(settings.storage_root, settings.admin_storage_subdir).mkdir(parents=True, exist_ok=True)
    Path(settings.storage_root, settings.manual_storage_subdir).mkdir(parents=True, exist_ok=True)


def sanitize_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format file tidak didukung. Gunakan CSV/XLSX/XLS.")
    return suffix


def save_upload_file(upload_file: UploadFile, *, target_subdir: str) -> str:
    ensure_storage_dirs()
    suffix = sanitize_suffix(upload_file.filename or "")
    safe_name = f"{uuid4().hex}{suffix}"
    destination = Path(settings.storage_root) / target_subdir / safe_name
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return str(destination.resolve())


def remove_file_if_exists(file_path: str) -> None:
    try:
        p = Path(file_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass


def serialize_file(file_obj: ExcelFile) -> dict:
    return {
        "id": file_obj.id,
        "file_name": file_obj.file_name,
        "original_name": file_obj.original_name,
        "file_path": file_obj.file_path,
        "upload_date": file_obj.upload_date,
        "uploaded_by": file_obj.uploaded_by,
        "uploaded_by_username": file_obj.uploader.username if file_obj.uploader else None,
        "source_type": file_obj.source_type,
        "is_active": file_obj.is_active,
    }


def create_file_record(
    db: Session,
    *,
    file_name: str,
    original_name: str | None,
    file_path: str,
    uploader: User,
    source_type: FileSourceType,
    is_active: bool = True,
) -> ExcelFile:
    file_obj = ExcelFile(
        file_name=file_name,
        original_name=original_name,
        file_path=file_path,
        uploaded_by=uploader.id,
        source_type=source_type,
        is_active=is_active,
    )
    db.add(file_obj)
    db.commit()
    db.refresh(file_obj)
    return file_obj
