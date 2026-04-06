from __future__ import annotations

from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataFile, DataRecord, User, UserRole
from app.services.legacy_logic import (
    ProcessParams,
    build_dashboard_payload,
    build_detail_agent_payload,
    build_priority_agent_detail_payload,
)


def get_file_for_user(db: Session, user: User, active_file_id: int) -> DataFile:
    file_obj = db.get(DataFile, active_file_id)
    if not file_obj or not file_obj.is_active:
        raise HTTPException(status_code=404, detail="Data tidak ditemukan atau sudah tidak aktif.")
    return file_obj


def get_active_file_from_header(
    *,
    db: Session,
    user: User,
    x_active_file_id: Optional[str],
) -> DataFile:
    if not x_active_file_id:
        raise HTTPException(status_code=400, detail="Belum ada data aktif. Pilih data dari dropdown dulu.")
    try:
        active_file_id = int(x_active_file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="X-Active-File-Id harus berupa angka.") from exc
    return get_file_for_user(db, user, active_file_id)


@lru_cache(maxsize=32)
def _load_dataframe_cached(file_id: int, version_token: str) -> pd.DataFrame:
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        stmt = (
            select(DataRecord)
            .where(DataRecord.file_id == file_id)
            .order_by(DataRecord.call_date.asc(), DataRecord.id.asc())
        )
        rows = db.scalars(stmt).all()
        records = []
        for row in rows:
            records.append({
                "call_date": row.call_date,
                "metadata_dateCall": row.call_datetime,
                "metadata_teamLeader": row.team_leader,
                "metadata_namaAgent": row.agent_name,
                "metadata_callResult": row.call_result,
                "duration": row.duration_seconds,
                "metadata_idCustomer": row.customer_id,
                "metadata_resultLov3": row.lov3_result,
                "sentiment_category": row.sentiment_category,
                "sentiment_reason": row.sentiment_reason,
                "raw_data_greetings_open": row.raw_data_greetings_open,
                "raw_data_say_acc": row.raw_data_say_acc,
                "raw_data_agent_name": row.raw_data_agent_name,
                "raw_data_cust_name": row.raw_data_cust_name,
                "raw_data_unit_cust": row.raw_data_unit_cust,
                "raw_data_kontrak_cust": row.raw_data_kontrak_cust,
                "raw_data_choice_cust": row.raw_data_choice_cust,
                "raw_data_greetings_close": row.raw_data_greetings_close,
                "raw_data_say_benefit": row.raw_data_say_benefit,
                "raw_data_do_simulasi": row.raw_data_do_simulasi,
                "raw_data_say_include_angsuran": row.raw_data_say_include_angsuran,
                "raw_data_say_segmentation_offer_range": row.raw_data_say_segmentation_offer_range,
                "raw_data_say_ref_contract_stat": row.raw_data_say_ref_contract_stat,
            })
        return pd.DataFrame.from_records(records)
    finally:
        db.close()


def load_dataframe_for_file(file_obj: DataFile) -> pd.DataFrame:
    version_token = f"{file_obj.upload_date.isoformat()}::{file_obj.row_count}"
    return _load_dataframe_cached(file_obj.id, version_token)


def build_meta_for_user(db: Session, file_obj: DataFile, user: User) -> dict:
    if user.role == UserRole.tl:
        tl_name = (user.tl_name or "").strip()
        agent_rows = db.scalars(
            select(DataRecord.agent_name)
            .where(DataRecord.file_id == file_obj.id, DataRecord.team_leader == tl_name)
            .distinct()
            .order_by(DataRecord.agent_name.asc())
        ).all()
        return {
            "tl_list": [tl_name] if tl_name else [],
            "agents_by_tl": {tl_name: list(agent_rows)} if tl_name else {},
            "locked_tl": tl_name,
        }

    tl_rows = db.scalars(
        select(DataRecord.team_leader)
        .where(DataRecord.file_id == file_obj.id)
        .distinct()
        .order_by(DataRecord.team_leader.asc())
    ).all()
    payload = {"tl_list": list(tl_rows), "agents_by_tl": {}, "locked_tl": None}
    for tl_name in tl_rows:
        agent_rows = db.scalars(
            select(DataRecord.agent_name)
            .where(DataRecord.file_id == file_obj.id, DataRecord.team_leader == tl_name)
            .distinct()
            .order_by(DataRecord.agent_name.asc())
        ).all()
        payload["agents_by_tl"][tl_name] = list(agent_rows)
    return payload


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
