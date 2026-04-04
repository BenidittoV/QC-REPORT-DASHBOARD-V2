from collections import OrderedDict
from typing import Optional

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CallRecord, ExcelFile, FileIngestStatus, FileSourceType, User, UserRole
from app.services.legacy_logic import (
    ProcessParams,
    build_dashboard_payload,
    build_detail_agent_payload,
    build_priority_agent_detail_payload,
)

_DF_CACHE: "OrderedDict[tuple[int, str | None, int], pd.DataFrame]" = OrderedDict()
_DF_CACHE_MAXSIZE = 8


def _cache_key(file_obj: ExcelFile) -> tuple[int, str | None, int]:
    return (
        file_obj.id,
        file_obj.processed_at.isoformat() if file_obj.processed_at else None,
        file_obj.row_count or 0,
    )


def _cache_get(key: tuple[int, str | None, int]) -> pd.DataFrame | None:
    df = _DF_CACHE.get(key)
    if df is None:
        return None
    _DF_CACHE.move_to_end(key)
    return df


def _cache_set(key: tuple[int, str | None, int], df: pd.DataFrame) -> None:
    _DF_CACHE[key] = df
    _DF_CACHE.move_to_end(key)
    while len(_DF_CACHE) > _DF_CACHE_MAXSIZE:
        _DF_CACHE.popitem(last=False)


def _ensure_file_ready(file_obj: ExcelFile) -> None:
    if file_obj.ingest_status == FileIngestStatus.ready:
        return
    if file_obj.ingest_status == FileIngestStatus.failed:
        raise HTTPException(
            status_code=409,
            detail=f"File gagal diproses. Detail: {file_obj.ingest_error or 'tidak diketahui'}",
        )
    raise HTTPException(
        status_code=409,
        detail="File masih diproses. Tunggu hingga ingest selesai.",
    )


def get_file_for_user(db: Session, user: User, active_file_id: int) -> ExcelFile:
    file_obj = db.get(ExcelFile, active_file_id)
    if not file_obj or not file_obj.is_active:
        raise HTTPException(status_code=404, detail="File tidak ditemukan atau tidak aktif.")

    if user.role == UserRole.tl and file_obj.source_type == FileSourceType.admin:
        _ensure_file_ready(file_obj)
        return file_obj

    if user.role == UserRole.tl and file_obj.uploaded_by != user.id:
        raise HTTPException(
            status_code=403,
            detail="TL hanya boleh memakai file admin atau file manual miliknya sendiri.",
        )

    _ensure_file_ready(file_obj)
    return file_obj


def get_active_file_from_header(
    *,
    db: Session,
    user: User,
    x_active_file_id: Optional[str],
) -> ExcelFile:
    if not x_active_file_id:
        raise HTTPException(
            status_code=400,
            detail="Belum ada file aktif. Pilih berkas admin atau upload manual dulu.",
        )

    try:
        active_file_id = int(x_active_file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Active-File-Id harus berupa angka.") from exc

    return get_file_for_user(db, user, active_file_id)


def load_dataframe_for_file(db: Session, file_obj: ExcelFile) -> pd.DataFrame:
    _ensure_file_ready(file_obj)

    key = _cache_key(file_obj)
    cached = _cache_get(key)
    if cached is not None:
        return cached.copy(deep=False)

    rows = db.scalars(
        select(CallRecord)
        .where(CallRecord.file_id == file_obj.id)
        .order_by(CallRecord.row_number.asc())
    ).all()

    payloads = [row.payload_json or {} for row in rows]
    df = pd.DataFrame(payloads)

    _cache_set(key, df)
    return df.copy(deep=False)


def build_meta_for_user(file_obj: ExcelFile, user: User) -> dict:
    _ensure_file_ready(file_obj)

    meta = file_obj.meta_json or {"tl_list": [], "agents_by_tl": {}}
    agents_by_tl = meta.get("agents_by_tl") or {}
    available_months = file_obj.available_months_json or []

    if user.role == UserRole.tl:
        tl_name = user.tl_name or ""
        return {
            "tl_list": [tl_name],
            "agents_by_tl": {tl_name: agents_by_tl.get(tl_name, [])},
            "locked_tl": tl_name,
            "available_months": available_months,
        }

    return {
        "tl_list": meta.get("tl_list") or [],
        "agents_by_tl": agents_by_tl,
        "available_months": available_months,
    }


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