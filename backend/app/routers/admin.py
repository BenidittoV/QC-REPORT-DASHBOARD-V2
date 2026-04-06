from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_admin, get_db
from app.models import DataFile, User, UserRole
from app.schemas import FileUpdate, UserCreate, UserUpdate
from app.security import hash_password
from app.services.file_service import create_file_record_from_upload, remove_file_dataset, serialize_file

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    total_users = db.query(User).count()
    total_tl = db.query(User).filter(User.role == UserRole.tl).count()
    total_files = db.query(DataFile).count()
    total_rows = db.query(DataFile).with_entities(DataFile.row_count).all()
    return {
        "total_users": total_users,
        "total_tl": total_tl,
        "total_files": total_files,
        "total_rows": int(sum(item[0] or 0 for item in total_rows)),
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

    if payload.role == UserRole.tl and not (payload.tl_name or "").strip():
        raise HTTPException(status_code=400, detail="tl_name wajib diisi untuk role TL.")

    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        tl_name=(payload.tl_name or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True}


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
        existing = db.scalar(select(User).where(User.username == new_username, User.id != user_id))
        if existing:
            raise HTTPException(status_code=400, detail="Username sudah dipakai.")
        user.username = new_username

    if payload.password:
        user.password_hash = hash_password(payload.password)

    if payload.role is not None:
        user.role = payload.role

    if payload.role == UserRole.tl or user.role == UserRole.tl:
        if payload.tl_name is not None:
            if not payload.tl_name.strip():
                raise HTTPException(status_code=400, detail="tl_name tidak boleh kosong untuk role TL.")
            user.tl_name = payload.tl_name.strip()

    if user.role == UserRole.admin:
        user.tl_name = None

    db.commit()
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
        select(DataFile).options(selectinload(DataFile.uploader)).order_by(DataFile.upload_date.desc())
    ).all()
    return [serialize_file(file_obj) for file_obj in files]


@router.post("/files")
def create_admin_file(
    file_name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if not file_name.strip():
        raise HTTPException(status_code=400, detail="Nama file wajib diisi.")
    file_obj = create_file_record_from_upload(
        db,
        file_name=file_name.strip(),
        upload_file=file,
        uploader=admin,
    )
    db.refresh(file_obj)
    return {"ok": True, "file": serialize_file(file_obj)}


@router.put("/files/{file_id}")
def update_file(
    file_id: int,
    payload: FileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    file_obj = db.get(DataFile, file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    file_obj.file_name = payload.file_name.strip()
    db.commit()
    return {"ok": True}


@router.delete("/files/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    file_obj = db.get(DataFile, file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")
    remove_file_dataset(db, file_obj)
    return {"ok": True}
