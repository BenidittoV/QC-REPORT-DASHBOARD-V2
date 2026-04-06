from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, Query
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.services.analytics_service import (
    build_dashboard_for_user,
    build_detail_for_user,
    build_meta_for_user,
    build_priority_detail_for_user,
    get_active_file_from_header,
    load_dataframe_for_file,
)
from app.services.file_service import list_available_files_for_user

router = APIRouter(tags=["dashboard"])


@router.get("/files/available")
def available_admin_files(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return list_available_files_for_user(db)


@router.get("/meta")
def get_meta(
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)
    payload = build_meta_for_user(db=db, file_obj=file_obj, user=user)
    payload["file_name"] = file_obj.file_name
    payload["file_id"] = file_obj.id
    payload["row_count"] = file_obj.row_count
    return payload


@router.post("/process")
def process(
    body: dict = Body(default_factory=dict),
    x_active_file_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    file_obj = get_active_file_from_header(db=db, user=user, x_active_file_id=x_active_file_id)
    df = load_dataframe_for_file(file_obj)
    payload = build_dashboard_for_user(df, user, body or {})
    payload["file_name"] = file_obj.file_name
    payload["file_id"] = file_obj.id
    payload["row_count"] = file_obj.row_count
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
    df = load_dataframe_for_file(file_obj)
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
    df = load_dataframe_for_file(file_obj)
    return build_priority_detail_for_user(df, user, table_type=table_type, agent=agent, month=month)
