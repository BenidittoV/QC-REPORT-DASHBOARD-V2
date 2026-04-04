from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Header, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import ExcelFile, FileIngestStatus, FileSourceType, User
from app.services.analytics_service import (
    build_dashboard_for_user,
    build_detail_for_user,
    build_meta_for_user,
    build_priority_detail_for_user,
    get_active_file_from_header,
    load_dataframe_for_file,
)
from app.services.file_service import create_file_record, save_upload_file, serialize_file
from app.services.ingest_service import ingest_file_into_database

router = APIRouter(tags=["dashboard"])


@router.get("/files/available")
def available_admin_files(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    files = db.scalars(
        select(ExcelFile)
        .where(
            ExcelFile.is_active.is_(True),
            ExcelFile.source_type == FileSourceType.admin,
            ExcelFile.ingest_status == FileIngestStatus.ready,
        )
        .order_by(ExcelFile.upload_date.desc())
    ).all()

    return [serialize_file(file_obj) for file_obj in files]


@router.post("/upload")
def manual_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    saved_path = save_upload_file(file, target_subdir="manual")
    file_obj = create_file_record(
        db,
        file_name=Path(file.filename or "manual_upload").stem,
        original_name=file.filename,
        file_path=saved_path,
        uploader=user,
        source_type=FileSourceType.tl_manual,
        is_active=True,
    )

    file_obj = ingest_file_into_database(db, file_obj)

    return {
        "ok": True,
        "file_id": file_obj.id,
        "file_name": file_obj.file_name,
        "rows": file_obj.row_count,
        "columns": file_obj.column_count,
    }


@router.get("/meta")
def get_meta(
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)

    payload = build_meta_for_user(file_obj, user)
    payload["file_name"] = file_obj.file_name
    payload["file_id"] = file_obj.id
    payload["source_type"] = file_obj.source_type
    payload["row_count"] = file_obj.row_count
    payload["column_count"] = file_obj.column_count
    return payload


@router.post("/process")
def process(
    body: dict = Body(default_factory=dict),
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)
    df = load_dataframe_for_file(db, file_obj)

    payload = build_dashboard_for_user(df, user, body or {})
    payload["file_name"] = file_obj.file_name
    payload["file_id"] = file_obj.id
    payload["source_type"] = file_obj.source_type
    return payload


@router.get("/detail-agent")
def detail_agent(
    agent: str = Query(...),
    month: Optional[str] = Query(None),
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)
    df = load_dataframe_for_file(db, file_obj)
    return build_detail_for_user(df, user, agent=agent, month=month)


@router.get("/priority-agent-detail")
def priority_agent_detail(
    table_type: str = Query(..., pattern="^(t1|t2)$"),
    agent: str = Query(...),
    month: Optional[str] = Query(None),
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)
    df = load_dataframe_for_file(db, file_obj)
    return build_priority_detail_for_user(df, user, table_type=table_type, agent=agent, month=month)