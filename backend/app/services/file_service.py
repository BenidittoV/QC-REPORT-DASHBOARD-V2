from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import DataFile, DataRecord, User


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
ASPECT_COLUMNS = [
    "raw_data_greetings_open",
    "raw_data_say_acc",
    "raw_data_agent_name",
    "raw_data_cust_name",
    "raw_data_unit_cust",
    "raw_data_kontrak_cust",
    "raw_data_choice_cust",
    "raw_data_greetings_close",
    "raw_data_say_benefit",
    "raw_data_do_simulasi",
    "raw_data_say_include_angsuran",
    "raw_data_say_segmentation_offer_range",
    "raw_data_say_ref_contract_stat",
]


def sanitize_suffix(filename: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Format file tidak didukung. Gunakan CSV/XLSX/XLS.")
    return suffix


def read_uploaded_dataframe(upload_file: UploadFile) -> pd.DataFrame:
    suffix = sanitize_suffix(upload_file.filename or "")
    payload = upload_file.file.read()
    buffer = io.BytesIO(payload)
    try:
        if suffix == ".csv":
            return pd.read_csv(buffer)
        return pd.read_excel(buffer)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File gagal dibaca: {exc}") from exc


def normalize_to_binary(value) -> int:
    if pd.isna(value):
        return 0
    if isinstance(value, (int, float)):
        return 1 if float(value) > 0 else 0
    text = str(value).strip().lower()
    if text in {"", "0", "false", "tidak", "no", "none", "nan", "null"}:
        return 0
    return 1


def parse_metadata_datecall(series: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    s = series.fillna("").astype(str).str.strip()
    bulan = {
        "januari": "01", "februari": "02", "maret": "03", "april": "04",
        "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
        "september": "09", "oktober": "10", "november": "11", "desember": "12",
    }
    s_low = s.str.lower()
    for nama, mm in bulan.items():
        s_low = s_low.str.replace(fr"\b{nama}\b", mm, regex=True)
    s_low = s_low.str.replace(r"^(\d{1,2})\s+(\d{2})\s+(\d{4})\s+", r"\1-\2-\3 ", regex=True)
    parsed = pd.to_datetime(s_low, format="%d-%m-%Y %H:%M:%S", errors="coerce")
    if parsed.notna().any():
        return parsed
    return pd.to_datetime(series, errors="coerce")


def parse_duration_seconds(series: pd.Series) -> pd.Series:
    def _parse(v):
        if pd.isna(v):
            return None
        if isinstance(v, (int, float)):
            val = float(v)
            return val if val >= 0 else None
        s = str(v).strip()
        if not s or s.lower() in {"nan", "none", "null"}:
            return None
        if ":" in s:
            parts = s.split(":")
            try:
                parts = [int(float(x)) for x in parts]
                if len(parts) == 2:
                    return float(parts[0] * 60 + parts[1])
                if len(parts) == 3:
                    return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
            except Exception:
                return None
        try:
            val = float(s.replace(",", "."))
            return val if val >= 0 else None
        except Exception:
            return None

    return series.apply(_parse)


def _require_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Kolom wajib tidak ditemukan: {', '.join(missing)}")


def prepare_records_dataframe(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    _require_columns(df, ["metadata_teamLeader", "metadata_namaAgent", "metadata_callResult"])

    if "metadata_dateCall" in df.columns:
        dt_series = parse_metadata_datecall(df["metadata_dateCall"])
    else:
        dt_series = pd.Series(pd.NaT, index=df.index)

    if "call_date" in df.columns:
        call_date = pd.to_datetime(df["call_date"], errors="coerce")
    else:
        call_date = dt_series.dt.floor("D")

    missing_date = call_date.isna() & dt_series.notna()
    if missing_date.any():
        call_date.loc[missing_date] = dt_series.loc[missing_date].dt.floor("D")

    df_out = pd.DataFrame({
        "call_date": call_date.dt.date,
        "call_datetime": dt_series,
        "team_leader": df["metadata_teamLeader"].fillna("").astype(str).str.strip(),
        "agent_name": df["metadata_namaAgent"].fillna("").astype(str).str.strip(),
        "call_result": df["metadata_callResult"].fillna("").astype(str).str.strip(),
        "customer_id": (
            df["metadata_idCustomer"]
            if "metadata_idCustomer" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        ),
        "lov3_result": (
            df["metadata_resultLov3"]
            if "metadata_resultLov3" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        ),
        "sentiment_category": (
            df["sentiment_category"]
            if "sentiment_category" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        ),
        "sentiment_reason": (
            df["sentiment_reason"]
            if "sentiment_reason" in df.columns
            else pd.Series([None] * len(df), index=df.index)
        ),
        "duration_seconds": parse_duration_seconds(
            df["duration"] if "duration" in df.columns else pd.Series([None] * len(df), index=df.index)
        ),
    })

    for col in ASPECT_COLUMNS:
        source = df[col] if col in df.columns else pd.Series([0] * len(df), index=df.index)
        df_out[col] = source.apply(normalize_to_binary)

    df_out["customer_id"] = df_out["customer_id"].where(pd.notna(df_out["customer_id"]), None)
    df_out["lov3_result"] = df_out["lov3_result"].where(pd.notna(df_out["lov3_result"]), None)
    df_out["sentiment_category"] = df_out["sentiment_category"].where(pd.notna(df_out["sentiment_category"]), None)
    df_out["sentiment_reason"] = df_out["sentiment_reason"].where(pd.notna(df_out["sentiment_reason"]), None)

    df_out = df_out[
        df_out["call_date"].notna()
        & df_out["team_leader"].ne("")
        & df_out["agent_name"].ne("")
        & df_out["call_result"].ne("")
    ].copy()

    if df_out.empty:
        raise HTTPException(status_code=400, detail="Setelah dibersihkan, tidak ada baris valid yang bisa disimpan.")

    return df_out


def serialize_file(file_obj: DataFile) -> dict:
    return {
        "id": file_obj.id,
        "file_name": file_obj.file_name,
        "original_name": file_obj.original_name,
        "upload_date": file_obj.upload_date,
        "uploaded_by": file_obj.uploaded_by,
        "uploaded_by_username": file_obj.uploader.username if file_obj.uploader else None,
        "is_active": file_obj.is_active,
        "row_count": file_obj.row_count,
        "tl_count": file_obj.tl_count,
        "agent_count": file_obj.agent_count,
        "start_date": file_obj.start_date,
        "end_date": file_obj.end_date,
    }


def list_available_files_for_user(db: Session) -> list[dict]:
    files = db.scalars(
        select(DataFile)
        .options(selectinload(DataFile.uploader))
        .where(DataFile.is_active.is_(True))
        .order_by(DataFile.upload_date.desc())
    ).all()
    return [serialize_file(item) for item in files]


def create_file_record_from_upload(
    db: Session,
    *,
    file_name: str,
    upload_file: UploadFile,
    uploader: User,
) -> DataFile:
    raw_df = read_uploaded_dataframe(upload_file)
    record_df = prepare_records_dataframe(raw_df)

    data_file = DataFile(
        file_name=file_name.strip(),
        original_name=upload_file.filename,
        uploaded_by=uploader.id,
        is_active=True,
        row_count=int(len(record_df)),
        tl_count=int(record_df["team_leader"].nunique()),
        agent_count=int(record_df["agent_name"].nunique()),
        start_date=record_df["call_date"].min(),
        end_date=record_df["call_date"].max(),
    )
    db.add(data_file)
    db.flush()

    rows = []
    for row in record_df.to_dict(orient="records"):
        row["file_id"] = data_file.id
        rows.append(row)

    chunk_size = 2000
    for start in range(0, len(rows), chunk_size):
        db.bulk_insert_mappings(DataRecord, rows[start:start + chunk_size])

    db.commit()
    db.refresh(data_file)
    return data_file


def remove_file_dataset(db: Session, file_obj: DataFile) -> None:
    db.delete(file_obj)
    db.commit()
