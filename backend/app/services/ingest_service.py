from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CallRecord, ExcelFile, FileIngestStatus
from app.services.file_service import remove_file_if_exists
from app.services.legacy_logic import build_meta_payload, ensure_date_and_dt, load_data, make_json_safe

TL_COL = "metadata_teamLeader"
AGENT_COL = "metadata_namaAgent"
CALLRESULT_COL = "metadata_callResult"
DATE_COL = "call_date"


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _safe_row_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): make_json_safe(value) for key, value in row.items()}


def _build_date_lookup(df: pd.DataFrame) -> dict[int, datetime]:
    lookup: dict[int, datetime] = {}
    try:
        prepared = ensure_date_and_dt(df)
        if DATE_COL in prepared.columns:
            for idx, value in prepared[DATE_COL].items():
                parsed = pd.to_datetime(value, errors="coerce")
                if not pd.isna(parsed):
                    lookup[int(idx)] = parsed.to_pydatetime()
    except Exception:
        pass
    return lookup


def _build_available_months(df: pd.DataFrame) -> list[str]:
    try:
        prepared = ensure_date_and_dt(df)
        if DATE_COL not in prepared.columns:
            return []
        months = (
            pd.to_datetime(prepared[DATE_COL], errors="coerce")
            .dropna()
            .dt.to_period("M")
            .astype(str)
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        return months
    except Exception:
        return []


def ingest_file_into_database(db: Session, file_obj: ExcelFile) -> ExcelFile:
    working = db.get(ExcelFile, file_obj.id)
    if not working:
        raise HTTPException(status_code=404, detail="File tidak ditemukan.")

    working.ingest_status = FileIngestStatus.processing
    working.ingest_error = None
    working.processed_at = None
    db.commit()
    db.refresh(working)

    try:
        if not working.file_path:
            raise ValueError("file_path kosong. Tidak ada sumber file untuk di-ingest.")

        df = load_data(working.file_path)
        if df is None or df.empty:
            raise ValueError("File kosong atau tidak memiliki baris data.")

        df = df.reset_index(drop=True)

        meta = build_meta_payload(df)
        available_months = _build_available_months(df)
        date_lookup = _build_date_lookup(df)

        agents_by_tl = meta.get("agents_by_tl") or {}
        unique_agents = sorted({agent for agents in agents_by_tl.values() for agent in agents})

        db.query(CallRecord).filter(CallRecord.file_id == working.id).delete(synchronize_session=False)

        batch: list[CallRecord] = []
        records = df.to_dict(orient="records")

        for idx, row in enumerate(records, start=1):
            payload = _safe_row_payload(row)
            parsed_dt = date_lookup.get(idx - 1)

            batch.append(
                CallRecord(
                    file_id=working.id,
                    row_number=idx,
                    tl_name=_clean_text(payload.get(TL_COL)),
                    agent_name=_clean_text(payload.get(AGENT_COL)),
                    call_result=_clean_text(payload.get(CALLRESULT_COL)),
                    call_date=parsed_dt.date() if parsed_dt else None,
                    month_key=parsed_dt.strftime("%Y-%m") if parsed_dt else None,
                    payload_json=payload,
                )
            )

            if len(batch) >= settings.ingest_chunk_size:
                db.add_all(batch)
                db.flush()
                batch.clear()

        if batch:
            db.add_all(batch)

        working.meta_json = meta
        working.available_months_json = available_months
        working.row_count = len(df.index)
        working.column_count = len(df.columns)
        working.tl_count = len(meta.get("tl_list") or [])
        working.agent_count = len(unique_agents)
        working.ingest_status = FileIngestStatus.ready
        working.ingest_error = None
        working.processed_at = datetime.utcnow()

        db.commit()
        db.refresh(working)

        if not settings.keep_uploaded_files and working.file_path:
            remove_file_if_exists(working.file_path)

        return working

    except Exception as exc:
        db.rollback()

        failed = db.get(ExcelFile, file_obj.id)
        if failed:
            failed.ingest_status = FileIngestStatus.failed
            failed.ingest_error = str(exc)[:2000]
            failed.processed_at = None
            db.commit()

        raise HTTPException(status_code=400, detail=f"Gagal memproses file: {exc}") from exc