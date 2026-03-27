from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.models import ExcelFile, FileSourceType, User, UserRole
from app.services.legacy_logic import (
    ProcessParams,
    build_dashboard_payload,
    build_detail_agent_payload,
    build_meta_payload,
    build_priority_agent_detail_payload,
    load_data,
)


def _cache_key(file_path: str) -> tuple[str, float]:
    path = Path(file_path)
    return (str(path.resolve()), path.stat().st_mtime)


@lru_cache(maxsize=32)
def _read_df_cached(file_path: str, mtime: float):
    return load_data(file_path)


def get_file_for_user(db: Session, user: User, active_file_id: int) -> ExcelFile:
    file_obj = db.get(ExcelFile, active_file_id)
    if not file_obj or not file_obj.is_active:
        raise HTTPException(status_code=404, detail="File tidak ditemukan atau tidak aktif.")

    if user.role == UserRole.tl and file_obj.source_type == FileSourceType.admin:
        return file_obj

    if user.role == UserRole.tl and file_obj.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="TL hanya boleh memakai file admin atau file manual miliknya sendiri.")

    return file_obj


def get_active_file_from_header(
    *,
    db: Session,
    user: User,
    x_active_file_id: Optional[str],
) -> ExcelFile:
    if not x_active_file_id:
        raise HTTPException(status_code=400, detail="Belum ada file aktif. Pilih berkas admin atau upload manual dulu.")
    try:
        active_file_id = int(x_active_file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Active-File-Id harus berupa angka.") from exc
    return get_file_for_user(db, user, active_file_id)


def load_dataframe_for_file(file_obj: ExcelFile):
    file_path, mtime = _cache_key(file_obj.file_path)
    return _read_df_cached(file_path, mtime)


def build_meta_for_user(df, user: User) -> dict:
    meta = build_meta_payload(df)
    if user.role == UserRole.tl:
        tl_name = user.tl_name or ""
        return {
            "tl_list": [tl_name],
            "agents_by_tl": {tl_name: meta.get("agents_by_tl", {}).get(tl_name, [])},
            "locked_tl": tl_name,
        }
    return meta


def build_dashboard_for_user(df, user: User, request_body: dict) -> dict:
    mode = request_body.get("mode") or "TL"
    selected_tl = request_body.get("selected_tl") or user.tl_name or ""
    selected_agent = request_body.get("selected_agent")
    selected_month = request_body.get("selected_month")
    allowed_call_types = request_body.get("allowed_call_types")

    if user.role == UserRole.tl:
        selected_tl = user.tl_name or ""

    params = ProcessParams(
        mode=mode,
        selected_tl=selected_tl,
        selected_agent=selected_agent,
        selected_month=selected_month,
        allowed_call_types=allowed_call_types,
    )
    payload = build_dashboard_payload(df, params)
    payload["locked_tl"] = user.tl_name
    payload["username"] = user.username
    return payload


def build_detail_for_user(df, user: User, *, agent: str, month: str | None):
    tl_name = user.tl_name or ""
    return build_detail_agent_payload(df, tl=tl_name, agent=agent, month=month)


def build_priority_detail_for_user(df, user: User, *, table_type: str, agent: str, month: str | None):
    params = ProcessParams(mode="TL", selected_tl=user.tl_name or "", selected_month=month)
    return build_priority_agent_detail_payload(df, params=params, table_type=table_type, agent=agent)
