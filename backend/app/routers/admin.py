from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_admin, get_db
from app.models import ExcelFile, FileSourceType, User, UserRole
from app.schemas import FileUpdate, UserCreate, UserUpdate
from app.security import hash_password
from app.services.file_service import (
    create_file_record,
    remove_file_if_exists,
    save_upload_file,
    serialize_file,
)
from app.services.ingest_service import ingest_file_into_database

router = APIRouter(prefix="/admin", tags=["admin"])


def _normalize_tl_name(*, role: UserRole, tl_name: str | None) -> str | None:
    if role == UserRole.admin:
        return None

    value = (tl_name or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="tl_name wajib diisi untuk role TL.")
    return value


@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    total_users = db.query(User).count()
    total_tl = db.query(User).filter(User.role == UserRole.tl).count()
    total_files = db.query(ExcelFile).count()
    total_admin_files = db.query(ExcelFile).filter(ExcelFile.source_type == FileSourceType.admin).count()
    total_manual_files = db.query(ExcelFile).filter(ExcelFile.source_type == FileSourceType.tl_manual).count()

    return {
        "total_users": total_users,
        "total_tl": total_tl,
        "total_files": total_files,
        "total_admin_files": total_admin_files,
        "total_manual_files": total_manual_files,
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    users = db.scalars(select(User).order_by(User.role, User.username)).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "tl_name": user.tl_name,
            "created_at": user.created_at,
        }
        for user in users
    ]


@router.post("/users")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    existing = db.scalar(select(User).where(User.username == payload.username.strip()))
    if existing:
        raise HTTPException(status_code=400, detail="Username sudah dipakai.")

    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        tl_name=_normalize_tl_name(role=payload.role, tl_name=payload.tl_name),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "ok": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "tl_name": user.tl_name,
            "created_at": user.created_at,
        },
    }


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    if payload.username is not None:
        new_username = payload.username.strip()
        if not new_username:
            raise HTTPException(status_code=400, detail="Username tidak boleh kosong.")
        existing = db.scalar(select(User).where(User.username == new_username, User.id != user_id))
        if existing:
            raise HTTPException(status_code=400, detail="Username sudah dipakai.")
        user.username = new_username

    if payload.password:
        user.password_hash = hash_password(payload.password)

    if user.username == "Admin" and payload.role is not None and payload.role != UserRole.admin:
        raise HTTPException(status_code=400, detail="Admin default tidak boleh diubah rolenya.")

    final_role = payload.role or user.role
    final_tl_name = user.tl_name

    if payload.role is not None:
        user.role = payload.role

    if final_role == UserRole.admin:
        final_tl_name = None
    else:
        if payload.tl_name is not None:
            final_tl_name = payload.tl_name.strip()
        if not final_tl_name:
            raise HTTPException(status_code=400, detail="tl_name wajib diisi untuk role TL.")

    user.tl_name = final_tl_name

    db.commit()
    db.refresh(user)
    return {"ok": True}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    if user.username == "Admin":
        raise HTTPException(status_code=400, detail="Admin default tidak boleh dihapus.")

    db.delete(user)
    db.commit()
    return {"ok": True}


@router.get("/files")
def list_files(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    files = db.scalars(
        select(ExcelFile)
        .options(selectinload(ExcelFile.uploader))
        .order_by(ExcelFile.upload_date.desc())
    ).all()
    return [serialize_file(file_obj) for file_obj in files]


@router.post("/files")
def create_admin_file(
    file_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    cleaned_name = file_name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="file_name tidak boleh kosong.")

    saved_path = save_upload_file(file, target_subdir="admin")
    file_obj = create_file_record(
        db,
        file_name=cleaned_name,
        original_name=file.filename,
        file_path=saved_path,
        uploader=admin,
        source_type=FileSourceType.admin,
        is_active=True,
    )

    file_obj = ingest_file_into_database(db, file_obj)
    db.refresh(file_obj)

    return {"ok": True, "file": serialize_file(file_obj)}


@router.put("/files/{file_id}")
def update_file(
    file_id: int,
    payload: FileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    file_obj = db.get(ExcelFile, file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

    cleaned_name = payload.file_name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=400, detail="file_name tidak boleh kosong.")

    file_obj.file_name = cleaned_name
    db.commit()
    return {"ok": True}


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    file_obj = db.get(ExcelFile, file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

    remove_file_if_exists(file_obj.file_path)
    db.delete(file_obj)
    db.commit()
    return {"ok": True}