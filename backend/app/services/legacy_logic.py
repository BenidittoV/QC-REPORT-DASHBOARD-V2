
from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

# =========================
# CONSTANTS
# =========================
TL_COL = "metadata_teamLeader"
AGENT_COL = "metadata_namaAgent"
CALLRESULT_COL = "metadata_callResult"
DATE_COL = "call_date"
DATETIME_COL = "metadata_dateCall"
DURATION_COL = "duration"
SENTIMENT_CATEGORY_COL = "sentiment_category"
SENTIMENT_REASON_COL = "sentiment_reason"
LOV3_COL = "metadata_resultLov3"

DEFAULT_ALLOWED_CALL_TYPES = [
    "M1 (Setuju dikirim hitungan)",
    "M2 (Negosiasi)",
    "M3 (Setuju dengan hitungan)",
    "Tidak Minat",
    "Appointment",
    "Warm Leads",
    "Pencairan Minus",
]

ASPECT_COLUMNS_CANDIDATES = [
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

ASPECT_FRIENDLY_NAMES = {
    "raw_data_greetings_open": "Salam Pembuka",
    "raw_data_say_acc": "Menyebut ACC",
    "raw_data_agent_name": "Menyebut Nama Agent",
    "raw_data_cust_name": "Menyebut Nama Customer",
    "raw_data_unit_cust": "Menyebut Unit Customer",
    "raw_data_kontrak_cust": "Menyebut Kontrak Customer",
    "raw_data_choice_cust": "Memuji Pelanggan Prioritas",
    "raw_data_greetings_close": "Salam Penutup",
    "raw_data_say_benefit": "Menyebut Benefit",
    "raw_data_do_simulasi": "Melakukan Simulasi",
    "raw_data_say_include_angsuran": "Menyebut Termasuk Asuransi",
    "raw_data_say_segmentation_offer_range": "Menyebut Persentase/ 70-80%",
    "raw_data_say_ref_contract_stat": "Menyebut Status Kontrak",
}

AUTH_TL_MAP = {
    "Elbina": "Elbina Debora",
    "Devi": "Devi Prastika",
    "Aldo": "Aldo Adhitya",
    "Feri": "Feri Noviyanto",
    "Ahim": "Trengginas Ahimsya",
    "Dewi": "Dewi Setyaningsih",
    "Era": "Eranio Dwi",
    "Ogie": "Ogie Prayoga",
    "Sisil": "Wiartika Sisil Mukaromah",
    "Fandri": "Fandri Ghozali",
}

AUTH_PASSWORDS = {
    "Elbina": "Hujan731Senja",
    "Devi": "Bulan482Kabut",
    "Aldo": "Angin594Pohon",
    "Feri": "Pasir318Gelombang",
    "Ahim": "Bintang927Langit",
    "Dewi": "Daun206Embun",
    "Era": "Rembulan173Hening",
    "Ogie": "Awan865Senyap",
    "Sisil": "Bintang521Cahaya",
    "Fandri": "Lampiob409Terang",
}

INVALID_TEXT_VALUES = {"", "nan", "none", "null", "nat"}


@dataclass
class ProcessParams:
    mode: str
    selected_tl: str
    selected_agent: Optional[str] = None
    selected_month: Optional[str] = None
    allowed_call_types: Optional[list[str]] = None


# =========================
# FILE / AUTH HELPERS
# =========================
def get_tl_for_username(username: str) -> Optional[str]:
    return AUTH_TL_MAP.get((username or "").strip())


def validate_credentials(username: str, password: str) -> bool:
    expected = AUTH_PASSWORDS.get((username or "").strip())
    return expected is not None and expected == password


def read_uploaded_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    lower_name = filename.lower()
    buffer = io.BytesIO(content)
    if lower_name.endswith(".csv"):
        return pd.read_csv(buffer)
    if lower_name.endswith((".xlsx", ".xls")):
        return pd.read_excel(buffer)
    raise ValueError("Format file tidak didukung. Gunakan CSV/XLSX/XLS.")


def load_data(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    return pd.read_excel(path)


# =========================
# GENERIC HELPERS
# =========================
def make_json_safe(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (dict, list, tuple)):
        return json.loads(json.dumps(value, default=str, ensure_ascii=False))
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    return value


def normalize_to_binary(v: Any) -> int:
    if pd.isna(v):
        return 0
    if isinstance(v, (int, float, np.integer, np.floating)):
        return 1 if float(v) > 0 else 0
    s = str(v).strip().lower()
    if s in {"", "nan", "none", "0", "false", "tidak", "no"}:
        return 0
    if s == "1":
        return 1
    return 1


def tier_from_percent(p: float) -> str:
    if p >= 80:
        return "A"
    if p >= 70:
        return "B"
    if p >= 60:
        return "C"
    return "D"


def safe_pct(binary_series: pd.Series) -> float:
    if binary_series is None or len(binary_series) == 0:
        return float("nan")
    return round(float(binary_series.mean() * 100.0), 2)


def compute_overall_from_aspects(df_subset: pd.DataFrame, aspect_cols: list[str]) -> float:
    if df_subset.empty or not aspect_cols:
        return float("nan")
    vals = [safe_pct(df_subset[c].apply(normalize_to_binary)) for c in aspect_cols if c in df_subset.columns]
    vals = [v for v in vals if not np.isnan(v)]
    return round(float(np.nanmean(vals)), 2) if vals else float("nan")


def count_and_total(df_subset: pd.DataFrame, col: str) -> tuple[int, int]:
    total = int(len(df_subset))
    if total == 0:
        return 0, 0
    hit = int(df_subset[col].apply(normalize_to_binary).sum())
    return hit, total


def format_hit_total(hit: int, total: int) -> str:
    if total <= 0:
        return "0/0"
    return f"{hit}/{total}"


def get_display_hours(df: pd.DataFrame, min_hour: int = 8, default_max_hour: int = 18) -> list[int]:
    if df is None or df.empty or "_dt_call" not in df.columns:
        return list(range(min_hour, default_max_hour + 1))

    hours = (
        df["_dt_call"]
        .dropna()
        .dt.hour
        .dropna()
        .astype(int)
        .tolist()
    )
    if not hours:
        return list(range(min_hour, default_max_hour + 1))

    max_hour = max(default_max_hour, max(hours))
    max_hour = min(max_hour, 23)
    return list(range(min_hour, max_hour + 1))


def get_daily_result_buckets() -> list[tuple[str, int, int]]:
    return [
        ("08-10", 8, 10),
        ("10-12", 10, 12),
        ("12-13", 12, 13),
        ("13-15", 13, 15),
        ("15-16", 15, 16),
        ("16-18", 16, 18),
    ]


def _norm_text(x: Any) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip().lower()


def _compact(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum())


def is_warmleads_value(x: Any) -> bool:
    v = _compact(_norm_text(x))
    return v in {"warmleads", "warmlead"}


def agent_positive_mask(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.lower()
    m_mask = s.str.contains(r"\bm1\b|\bm2\b|\bm3\b", na=False)
    w_mask = s.str.contains(r"warm\s*leads?|warmleads?", na=False)
    return m_mask | w_mask


def format_seconds_mmss(sec: float) -> str:
    if sec is None or (isinstance(sec, float) and np.isnan(sec)):
        return "-"
    total = int(round(float(sec)))
    m = total // 60
    s = total % 60
    return f"{m}:{s:02d}"


def parse_duration_seconds(v: Any) -> float:
    if pd.isna(v):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        val = float(v)
        return val if val >= 0 else np.nan
    s = str(v).strip()
    if s == "" or s.lower() in {"nan", "none"}:
        return np.nan
    if ":" in s:
        parts = s.split(":")
        try:
            parts = [int(float(x)) for x in parts]
            if len(parts) == 2:
                return float(parts[0] * 60 + parts[1])
            if len(parts) == 3:
                return float(parts[0] * 3600 + parts[1] * 60 + parts[2])
        except Exception:
            return np.nan
    try:
        val = float(s.replace(",", "."))
        return val if val >= 0 else np.nan
    except Exception:
        return np.nan


def week_ranges_sun_sat_for_month(year: int, month: int):
    month_start = pd.Timestamp(year=year, month=month, day=1)
    month_end = month_start + pd.offsets.MonthEnd(1)
    days_to_sun = (6 - month_start.weekday()) % 7
    first_sunday = month_start + pd.Timedelta(days=days_to_sun)

    ranges = []
    if first_sunday > month_start:
        ranges.append((month_start, first_sunday - pd.Timedelta(days=1)))

    cur = first_sunday
    while cur <= month_end:
        start = cur
        end = min(cur + pd.Timedelta(days=6), month_end)
        if start == end and start.weekday() == 6:
            break
        ranges.append((start, end))
        cur = cur + pd.Timedelta(days=7)
    return ranges


# =========================
# DATA NORMALIZATION
# =========================
def normalize_identity_cols(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if TL_COL in out.columns:
        out[TL_COL] = out[TL_COL].fillna("").astype(str).str.strip()
    if AGENT_COL in out.columns:
        out[AGENT_COL] = out[AGENT_COL].fillna("").astype(str).str.strip()
    if TL_COL in out.columns:
        out = out[(out[TL_COL] != "") & (~out[TL_COL].str.lower().isin(INVALID_TEXT_VALUES))]
    if AGENT_COL in out.columns:
        out = out[(out[AGENT_COL] != "") & (~out[AGENT_COL].str.lower().isin(INVALID_TEXT_VALUES))]
    return out


def normalize_identity_values(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if TL_COL in out.columns:
        out[TL_COL] = out[TL_COL].fillna("").astype(str).str.strip()
    if AGENT_COL in out.columns:
        out[AGENT_COL] = out[AGENT_COL].fillna("").astype(str).str.strip()
    return out


def parse_metadata_datecall(series: pd.Series) -> pd.Series:
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
    return pd.to_datetime(s_low, format="%d-%m-%Y %H:%M:%S", errors="coerce")


def ensure_date_and_dt(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if DATETIME_COL in out.columns:
        out["_dt_call"] = parse_metadata_datecall(out[DATETIME_COL])
    else:
        out["_dt_call"] = pd.NaT

    if DATE_COL in out.columns:
        out[DATE_COL] = pd.to_datetime(out[DATE_COL], errors="coerce")
    else:
        if out["_dt_call"].notna().any():
            out[DATE_COL] = out["_dt_call"].dt.floor("D")
        else:
            raise ValueError(f"Tidak ada '{DATE_COL}' dan '{DATETIME_COL}' juga tidak tersedia/valid.")

    if DATE_COL in out.columns:
        missing_date = out[DATE_COL].isna()
        if missing_date.any() and out["_dt_call"].notna().any():
            out.loc[missing_date, DATE_COL] = out.loc[missing_date, "_dt_call"].dt.floor("D")

    out = out.dropna(subset=[DATE_COL]).copy()
    if out.empty:
        raise ValueError("Semua tanggal gagal diparse. Pastikan format tanggal valid.")

    return out


def filter_call_types(df: pd.DataFrame, allowed: Optional[list[str]] = None) -> pd.DataFrame:
    if CALLRESULT_COL not in df.columns:
        return df.copy()
    allowed = allowed or DEFAULT_ALLOWED_CALL_TYPES
    allowed_lower = {a.strip().lower() for a in allowed}
    mask = df[CALLRESULT_COL].fillna("").astype(str).str.strip().str.lower().isin(allowed_lower)
    return df[mask].copy()


def build_meta_payload(df: pd.DataFrame) -> dict:
    df_clean = normalize_identity_cols(df)
    tl_list = sorted(df_clean[TL_COL].drop_duplicates().tolist()) if TL_COL in df_clean.columns else []
    agents_by_tl: dict[str, list[str]] = {}
    if TL_COL in df_clean.columns and AGENT_COL in df_clean.columns:
        for tl, grp in df_clean.groupby(TL_COL):
            agents = grp[AGENT_COL].drop_duplicates().tolist()
            agents_by_tl[tl] = sorted(agents)
    return {"tl_list": tl_list, "agents_by_tl": agents_by_tl}


# =========================
# INTEREST MASKS
# =========================
def interest_masks(df: pd.DataFrame):
    req_sent = [SENTIMENT_CATEGORY_COL, SENTIMENT_REASON_COL, CALLRESULT_COL]
    if all(c in df.columns for c in req_sent):
        dfx = df.copy()
        dfx[SENTIMENT_CATEGORY_COL] = dfx[SENTIMENT_CATEGORY_COL].astype(str).str.strip().str.lower()
        dfx[SENTIMENT_REASON_COL] = dfx[SENTIMENT_REASON_COL].astype(str).str.lower()
        ai_mask = dfx[SENTIMENT_CATEGORY_COL].isin(["potensi berminat", "ragu-ragu"])
        agent_mask = agent_positive_mask(dfx[CALLRESULT_COL])
        keywords = ["pikir-pikir", "pikir pikir", "pikir", "pertimbangkan", "diskusi", "diskusikan"]
        pattern = "|".join(keywords)
        rule3 = (
            (~agent_mask)
            & (dfx[SENTIMENT_CATEGORY_COL] == "tidak berminat")
            & (dfx[SENTIMENT_REASON_COL].str.contains(pattern, na=False))
        )
        actual_mask = ai_mask | agent_mask | rule3
        return {"mode": "sentiment", "ai_mask": ai_mask, "agent_mask": agent_mask, "actual_mask": actual_mask}

    req_lov3 = [LOV3_COL, CALLRESULT_COL]
    if all(c in df.columns for c in req_lov3):
        dfx = df.copy()
        ai_mask = dfx[LOV3_COL].apply(is_warmleads_value)
        agent_mask = agent_positive_mask(dfx[CALLRESULT_COL])
        actual_mask = ai_mask | agent_mask
        return {"mode": "lov3", "ai_mask": ai_mask, "agent_mask": agent_mask, "actual_mask": actual_mask}

    return None


# =========================
# BUILDERS
# =========================
# =========================
# BULANAN / HARIAN SUPPORT
# =========================
def split_calendar_month_ranges(year: int, month: int) -> dict:
    last_day = int(pd.Timestamp(year=year, month=month, day=1).days_in_month)

    if last_day == 31:
        p1_start, p1_end = 1, 16
        p2_start, p2_end = 17, 31
    else:
        p1_start, p1_end = 1, 15
        p2_start, p2_end = 16, last_day

    return {
        "last_day": last_day,
        "p1_start": p1_start,
        "p1_end": p1_end,
        "p2_start": p2_start,
        "p2_end": p2_end,
        "label_1": f"Periode 1 ({p1_start}–{p1_end})",
        "label_2": f"Periode 2 ({p2_start}–{p2_end})",
    }


def build_daily_interest_for_period(scope_df: pd.DataFrame, actual_mask: pd.Series, start_day: int, end_day: int) -> list[dict]:
    if actual_mask is None or scope_df.empty:
        return []

    d = scope_df.copy()
    d["_day_dt"] = pd.to_datetime(d[DATE_COL]).dt.floor("D")
    d["_day_num"] = d["_day_dt"].dt.day
    d = d[(d["_day_num"] >= start_day) & (d["_day_num"] <= end_day)].copy()
    if d.empty:
        return []

    d["_is_interest"] = actual_mask.reindex(d.index).fillna(False).astype(bool).values
    daily = (
        d.groupby("_day_dt", as_index=False)
        .agg(jumlah_minat=("_is_interest", "sum"), jumlah_rekaman=("_is_interest", "size"))
    )
    daily["rate_minat"] = np.nan
    valid = daily["jumlah_rekaman"] > 0
    daily.loc[valid, "rate_minat"] = (daily.loc[valid, "jumlah_minat"] / daily.loc[valid, "jumlah_rekaman"] * 100.0).round(2)

    rows = []
    for _, row in daily.sort_values("_day_dt").iterrows():
        rows.append({
            "date": str(pd.Timestamp(row["_day_dt"]).date()),
            "minat": int(row["jumlah_minat"]),
            "rekaman": int(row["jumlah_rekaman"]),
            "rate": None if pd.isna(row["rate_minat"]) else float(row["rate_minat"]),
        })
    return rows


def build_agent_daily_presence_summary(scope_df: pd.DataFrame, actual_mask: pd.Series, active_days: list, allowed_missing_days: int = 2, invert: bool = False) -> list[dict]:
    if AGENT_COL not in scope_df.columns or scope_df.empty:
        return []

    d = scope_df.copy()
    d[AGENT_COL] = d[AGENT_COL].fillna("").astype(str).str.strip()
    d = d[(d[AGENT_COL] != "") & (d[AGENT_COL].str.lower() != "nan")].copy()
    if d.empty:
        return []

    d["_day_dt"] = pd.to_datetime(d[DATE_COL]).dt.floor("D")
    d["_is_interest"] = actual_mask.reindex(d.index).fillna(False).astype(bool).values

    total_active_days = len(active_days)
    if total_active_days == 0:
        return []

    rows = []
    for agent, da in d.groupby(AGENT_COL):
        hadir_days = int(da["_day_dt"].nunique())
        kosong_days = total_active_days - hadir_days
        jumlah_rekaman = int(len(da))
        jumlah_minat = int(da["_is_interest"].sum())
        jumlah_tidak_minat = jumlah_rekaman - jumlah_minat

        keep = kosong_days > allowed_missing_days if invert else kosong_days <= allowed_missing_days
        if keep:
            rows.append({
                "agent": str(agent),
                "hari_hadir": hadir_days,
                "hari_kosong": kosong_days,
                "minat": jumlah_minat,
                "tidak_minat": jumlah_tidak_minat,
                "rekaman": jumlah_rekaman,
            })

    rows = sorted(rows, key=lambda x: (-x["minat"], -x["rekaman"], x["hari_kosong"], x["agent"]))
    return rows


def build_daily_interest_chart_for_agent_group(scope_df: pd.DataFrame, actual_mask: pd.Series, selected_agents: set[str]) -> list[dict]:
    if not selected_agents:
        return []

    d = scope_df.copy()
    d[AGENT_COL] = d[AGENT_COL].fillna("").astype(str).str.strip()
    d = d[d[AGENT_COL].isin(selected_agents)].copy()
    if d.empty:
        return []

    d["_day_dt"] = pd.to_datetime(d[DATE_COL]).dt.floor("D")
    d["_is_interest"] = actual_mask.reindex(d.index).fillna(False).astype(bool).values

    daily = (
        d.groupby("_day_dt", as_index=False)
        .agg(jumlah_minat=("_is_interest", "sum"), jumlah_rekaman=("_is_interest", "size"))
    )
    daily["rate_minat"] = np.nan
    valid = daily["jumlah_rekaman"] > 0
    daily.loc[valid, "rate_minat"] = (daily.loc[valid, "jumlah_minat"] / daily.loc[valid, "jumlah_rekaman"] * 100.0).round(2)

    rows = []
    for _, row in daily.sort_values("_day_dt").iterrows():
        rows.append({
            "date": str(pd.Timestamp(row["_day_dt"]).date()),
            "minat": int(row["jumlah_minat"]),
            "rekaman": int(row["jumlah_rekaman"]),
            "rate": None if pd.isna(row["rate_minat"]) else float(row["rate_minat"]),
        })
    return rows


def compute_hourly_reference_lines(baseline_df: pd.DataFrame, aspect_cols: list[str], entity_col: str, display_hours: list[int]) -> dict:
    result = {"upper": None, "lower": None, "kkm": None}
    if baseline_df is None or baseline_df.empty or entity_col not in baseline_df.columns:
        return result

    dfx = baseline_df.copy()
    dfx = ensure_date_and_dt(dfx)
    if "_dt_call" not in dfx.columns or dfx["_dt_call"].notna().sum() == 0:
        return result

    dfx[entity_col] = dfx[entity_col].fillna("").astype(str).str.strip()
    dfx = dfx[(dfx[entity_col] != "") & (dfx[entity_col].str.lower() != "nan")].copy()
    if dfx.empty:
        return result

    valid_hours = set(display_hours)
    dfx["_hour"] = dfx["_dt_call"].dt.hour
    dfx = dfx[dfx["_hour"].isin(valid_hours)].copy()
    if dfx.empty:
        return result

    entity_hour_values = []
    for (_, _), dsub in dfx.groupby([entity_col, "_hour"]):
        ov = compute_overall_from_aspects(dsub, aspect_cols)
        if not np.isnan(ov):
            entity_hour_values.append(float(ov))

    if not entity_hour_values:
        return result

    result["upper"] = round(float(np.nanmax(entity_hour_values)), 2)
    result["lower"] = round(float(np.nanmin(entity_hour_values)), 2)
    result["kkm"] = round(float(np.nanmean(entity_hour_values)), 2)
    return result


MINAT_CALLRESULT_EXACT = {
    "m1 (setuju dikirim hitungan)",
    "m2 (negosiasi)",
    "m3 (setuju dengan hitungan)",
}


def normalize_call_group(value: Any) -> Optional[str]:
    s = re.sub(r"\s+", " ", str(value or "").strip().lower())
    if s in MINAT_CALLRESULT_EXACT:
        return "Minat"
    if re.fullmatch(r"tidak\s*minat", s):
        return "Tidak Minat"
    if re.fullmatch(r"appointment", s):
        return "Appointment"
    return None

def build_result_table(scope_df: pd.DataFrame, time_mode: str, selected_month: Optional[str] = None) -> dict:
    aspect_cols = [c for c in ASPECT_COLUMNS_CANDIDATES if c in scope_df.columns]
    if not aspect_cols:
        return {"rows": [], "overall": None, "time_mode": time_mode, "aspect_cols": []}

    if time_mode == "Bulanan":
        dfm = scope_df[scope_df["_month"] == selected_month].copy() if selected_month else scope_df.copy()
        yy, mm = selected_month.split("-")
        yy, mm = int(yy), int(mm)
        week_ranges = week_ranges_sun_sat_for_month(yy, mm)

        rows = []
        for col in aspect_cols:
            row = {"aspek": ASPECT_FRIENDLY_NAMES.get(col, col), "col": col}
            for i, (ws, we) in enumerate(week_ranges, start=1):
                df_w = dfm[(dfm[DATE_COL] >= ws) & (dfm[DATE_COL] <= we)]
                hit, total = count_and_total(df_w, col)
                row[f"minggu_{i}"] = format_hit_total(hit, total)
            hit_m, total_m = count_and_total(dfm, col)
            pct_m = safe_pct(dfm[col].apply(normalize_to_binary))
            row["bulanan"] = format_hit_total(hit_m, total_m)
            row["pct"] = pct_m if not np.isnan(pct_m) else None
            row["grade"] = tier_from_percent(pct_m) if not np.isnan(pct_m) else "-"
            rows.append(row)

        rows.sort(key=lambda x: (x["pct"] if x["pct"] is not None else -1))
        overall = round(float(np.nanmean([r["pct"] for r in rows if r["pct"] is not None])), 2) if rows else None
        return {"rows": rows, "overall": overall, "num_weeks": len(week_ranges), "time_mode": "Bulanan", "aspect_cols": aspect_cols}

    dfm = scope_df.copy()
    if "_dt_call" not in dfm.columns:
        dfm["_dt_call"] = pd.NaT
    dfm["_hour"] = dfm["_dt_call"].dt.hour
    buckets = get_daily_result_buckets()
    outside_mask = (dfm["_hour"] < 8) | (dfm["_hour"] >= 18)
    has_outside = bool(outside_mask.fillna(False).any())

    rows = []
    for col in aspect_cols:
        row = {"aspek": ASPECT_FRIENDLY_NAMES.get(col, col), "col": col}
        for label, h0, h1 in buckets:
            d = dfm[(dfm["_hour"] >= h0) & (dfm["_hour"] < h1)]
            hit, total = count_and_total(d, col)
            row[label] = format_hit_total(hit, total)
        if has_outside:
            d_out = dfm[outside_mask.fillna(False)]
            hit_out, total_out = count_and_total(d_out, col)
            row["di_luar_08_18"] = format_hit_total(hit_out, total_out)
        hit_d, total_d = count_and_total(dfm, col)
        pct_d = safe_pct(dfm[col].apply(normalize_to_binary))
        row["harian"] = format_hit_total(hit_d, total_d)
        row["pct"] = pct_d if not np.isnan(pct_d) else None
        row["grade"] = tier_from_percent(pct_d) if not np.isnan(pct_d) else "-"
        rows.append(row)

    rows.sort(key=lambda x: (x["pct"] if x["pct"] is not None else -1))
    overall = round(float(np.nanmean([r["pct"] for r in rows if r["pct"] is not None])), 2) if rows else None
    return {"rows": rows, "overall": overall, "time_mode": "Harian", "has_outside": has_outside, "aspect_cols": aspect_cols}


def build_agent_interest_summary(scope_df: pd.DataFrame):
    if AGENT_COL not in scope_df.columns:
        return None
    im = interest_masks(scope_df)
    if im is None:
        return None
    actual_mask = im["actual_mask"]
    d = scope_df.copy()
    d[AGENT_COL] = d[AGENT_COL].fillna("").astype(str).str.strip()
    d = d[(d[AGENT_COL] != "") & (d[AGENT_COL].str.lower() != "nan")]
    m = actual_mask.reindex(d.index).fillna(False).astype(bool)
    d["_is_interest"] = m.values

    summary = (
        d.groupby(AGENT_COL, as_index=False)
        .agg(jumlah_minat=("_is_interest", "sum"), jumlah_rekaman=("_is_interest", "size"))
    )
    summary["jumlah_tidak_minat"] = summary["jumlah_rekaman"] - summary["jumlah_minat"]
    summary = summary.rename(columns={
        AGENT_COL: "agent",
        "jumlah_minat": "minat",
        "jumlah_tidak_minat": "tidak_minat",
        "jumlah_rekaman": "rekaman",
    }).sort_values(by=["minat", "rekaman"], ascending=[False, False])
    for c in ["minat", "tidak_minat", "rekaman"]:
        summary[c] = pd.to_numeric(summary[c], errors="coerce").fillna(0).astype(int)
    return summary.to_dict(orient="records")


def build_tl_agent_comparison(scope_df: pd.DataFrame, aspect_cols: list[str], top_n: int = 4):
    if AGENT_COL not in scope_df.columns or scope_df.empty:
        return None, None
    d = scope_df.copy()
    d[AGENT_COL] = d[AGENT_COL].fillna("").astype(str).str.strip()
    d = d[(d[AGENT_COL] != "") & (d[AGENT_COL].str.lower() != "nan")]
    if d.empty:
        return None, None

    rows = []
    for agent, da in d.groupby(AGENT_COL):
        agent_overall = compute_overall_from_aspects(da, aspect_cols)
        if np.isnan(agent_overall):
            continue
        aspek_scores = []
        for col in aspect_cols:
            bin_series = da[col].apply(normalize_to_binary)
            hit = int(bin_series.sum())
            total = int(len(da))
            pct = safe_pct(bin_series)
            if not np.isnan(pct):
                aspek_scores.append({"aspek": ASPECT_FRIENDLY_NAMES.get(col, col), "pct": float(pct), "hit": hit, "total": total})
        if not aspek_scores:
            continue

        aspek_asc = sorted(aspek_scores, key=lambda x: (x["pct"], x["aspek"]))
        aspek_desc = sorted(aspek_scores, key=lambda x: (-x["pct"], x["aspek"]))

        weak_n = ", ".join([f'{x["aspek"]} ({x["hit"]}/{x["total"]})' for x in aspek_asc[:top_n]])
        strong_n = ", ".join([f'{x["aspek"]} ({x["hit"]}/{x["total"]})' for x in aspek_desc[:top_n]])

        rows.append({
            "agent": agent,
            "rekaman": int(len(da)),
            "overall": round(float(agent_overall), 2),
            "aspek_lemah": weak_n,
            "aspek_kuat": strong_n,
        })

    if not rows:
        return None, None

    worst = sorted(rows, key=lambda x: (x["overall"], -x["rekaman"]))
    best = sorted(rows, key=lambda x: (-x["overall"], -x["rekaman"]))
    return worst, best



def _priority_table_records(scope_df: pd.DataFrame, table_type: str) -> list[dict]:
    if CALLRESULT_COL not in scope_df.columns:
        return []

    dfx = scope_df.copy()
    dfx[CALLRESULT_COL] = dfx[CALLRESULT_COL].fillna("").astype(str).str.strip()
    dfx["_call_group"] = dfx[CALLRESULT_COL].apply(normalize_call_group)

    customer_id_candidates = ["metadata_idCustomer", "metadata_customerId", "customer_id", "cust_id", "id_customer", "raw_data_kontrak_cust"]
    customer_id_col = next((c for c in customer_id_candidates if c in dfx.columns), None)

    if table_type == "t1":
        aspek = [c for c in [
            "raw_data_do_simulasi",
            "raw_data_say_segmentation_offer_range",
            "raw_data_say_benefit",
        ] if c in dfx.columns]
        base = dfx[dfx["_call_group"] == "Minat"].copy()

        if not aspek or base.empty:
            return []

        def _aspect_value(row):
            missing = [ASPECT_FRIENDLY_NAMES.get(col, col) for col in aspek if normalize_to_binary(row[col]) == 0]
            return ", ".join(missing)

        aspect_field = "aspek_jarang"
        aspect_label = "Aspek Jarang Disebut"
    else:
        aspek = [c for c in [
            "raw_data_choice_cust",
            "raw_data_say_include_angsuran",
            "raw_data_do_simulasi",
        ] if c in dfx.columns]
        base = dfx[dfx["_call_group"] == "Tidak Minat"].copy()

        if not aspek or base.empty:
            return []

        base = base[base["raw_data_do_simulasi"].apply(normalize_to_binary) == 1].copy() if "raw_data_do_simulasi" in base.columns else base.iloc[0:0].copy()
        if base.empty:
            return []

        def _aspect_value(row):
            present = [ASPECT_FRIENDLY_NAMES.get(col, col) for col in aspek if normalize_to_binary(row[col]) == 1]
            return ", ".join(present)

        aspect_field = "aspek_hadir"
        aspect_label = "Aspek Sudah Disebut"

    base[aspect_field] = base.apply(_aspect_value, axis=1)
    base = base[base[aspect_field].str.strip() != ""].copy()
    if base.empty:
        return []

    cols = [AGENT_COL, CALLRESULT_COL]
    if customer_id_col:
        cols.append(customer_id_col)
    if DATETIME_COL in base.columns:
        cols.append(DATETIME_COL)
    cols.append(aspect_field)

    renamed = {
        AGENT_COL: "agent",
        CALLRESULT_COL: "call_result",
        aspect_field: aspect_label,
    }
    if DATETIME_COL in base.columns:
        renamed[DATETIME_COL] = "tanggal"
    if customer_id_col:
        renamed[customer_id_col] = "id_customer"

    records = base[cols].rename(columns=renamed).to_dict(orient="records")
    cleaned_records = []
    for rec in records:
        cleaned = {str(k): make_json_safe(v) for k, v in rec.items()}
        cleaned["agent"] = str(cleaned.get("agent", "")).strip()
        if cleaned["agent"]:
            cleaned_records.append(cleaned)
    return cleaned_records


def _summarize_priority_records(records: list[dict], table_type: str) -> list[dict]:
    if not records:
        return []

    df_rec = pd.DataFrame(records)
    if df_rec.empty or "agent" not in df_rec.columns:
        return []

    aspect_col = "Aspek Jarang Disebut" if table_type == "t1" else "Aspek Sudah Disebut"
    df_rec["agent"] = df_rec["agent"].fillna("").astype(str).str.strip()
    df_rec = df_rec[df_rec["agent"] != ""].copy()
    if df_rec.empty:
        return []

    rows = []
    for agent, grp in df_rec.groupby("agent"):
        ringkasan = "-"
        if aspect_col in grp.columns:
            exploded = (
                grp[aspect_col]
                .fillna("")
                .astype(str)
                .str.split(",")
                .explode()
                .astype(str)
                .str.strip()
            )
            exploded = exploded[exploded != ""]
            if not exploded.empty:
                counts = exploded.value_counts()
                ringkasan = ", ".join([f"{name} ({count})" for name, count in counts.head(4).items()])

        pelanggan_unik = None
        if "id_customer" in grp.columns:
            pelanggan_unik = int(
                grp["id_customer"]
                .fillna("")
                .astype(str)
                .str.strip()
                .replace("", np.nan)
                .dropna()
                .nunique()
            )

        rows.append({
            "agent": agent,
            "jumlah_call": int(len(grp)),
            "jumlah_customer": pelanggan_unik,
            "ringkasan_aspek": ringkasan,
            "table_type": table_type,
        })

    rows = sorted(rows, key=lambda x: (-x["jumlah_call"], -(x["jumlah_customer"] or 0), x["agent"]))
    return rows


def build_daily_aspect_agent_breakdown(scope_df: pd.DataFrame, result_rows: list[dict]) -> dict[str, list[dict]]:
    if scope_df.empty or not result_rows or AGENT_COL not in scope_df.columns:
        return {}

    dfm = scope_df.copy()
    if "_dt_call" not in dfm.columns:
        dfm["_dt_call"] = pd.NaT
    dfm["_hour"] = dfm["_dt_call"].dt.hour
    outside_mask = (dfm["_hour"] < 8) | (dfm["_hour"] >= 18)

    bucket_defs = [(label, (dfm["_hour"] >= h0) & (dfm["_hour"] < h1)) for label, h0, h1 in get_daily_result_buckets()]
    bucket_defs.append(("harian", pd.Series(True, index=dfm.index)))
    if bool(outside_mask.fillna(False).any()):
        bucket_defs.append(("di_luar_08_18", outside_mask.fillna(False)))

    breakdown: dict[str, list[dict]] = {}
    for row in result_rows:
        aspect_col = row.get("col")
        if not aspect_col or aspect_col not in dfm.columns:
            continue

        for bucket_key, mask in bucket_defs:
            subset = dfm[mask].copy()
            if subset.empty:
                breakdown[f"{aspect_col}__{bucket_key}"] = []
                continue

            grouped_rows = []
            for agent, grp in subset.groupby(AGENT_COL):
                agent_name = str(agent).strip()
                if not agent_name or agent_name.lower() == "nan":
                    continue
                hit = int(grp[aspect_col].apply(normalize_to_binary).sum())
                total = int(len(grp))
                grouped_rows.append({
                    "agent": agent_name,
                    "hit": hit,
                    "total": total,
                    "ratio": format_hit_total(hit, total),
                })

            grouped_rows = sorted(grouped_rows, key=lambda x: (-x["hit"], -x["total"], x["agent"]))
            breakdown[f"{aspect_col}__{bucket_key}"] = grouped_rows

    return breakdown


def build_priority_followup_tables(scope_df: pd.DataFrame):
    t1_records = _priority_table_records(scope_df, "t1")
    t2_records = _priority_table_records(scope_df, "t2")
    return _summarize_priority_records(t1_records, "t1"), _summarize_priority_records(t2_records, "t2")



def build_weekly_trend(scope_df: pd.DataFrame, baseline_df: pd.DataFrame, selected_month: str,
                       aspect_cols: list[str], entity_col: str, actual_mask=None):
    yy, mm = selected_month.split("-")
    yy, mm = int(yy), int(mm)
    week_ranges = week_ranges_sun_sat_for_month(yy, mm)

    weekly_sel = []
    for i, (ws, we) in enumerate(week_ranges, start=1):
        df_w = scope_df[(scope_df[DATE_COL] >= ws) & (scope_df[DATE_COL] <= we)]
        overall_w = compute_overall_from_aspects(df_w, aspect_cols)
        wm = int(actual_mask.loc[df_w.index].sum()) if actual_mask is not None and not df_w.empty else int(len(df_w))
        weekly_sel.append({
            "week": f"M{i}",
            "overall": overall_w if not np.isnan(overall_w) else None,
            "rekaman": int(len(df_w)),
            "wm": wm,
        })

    min_line = max_line = kkm_line = avg_selected = None
    if baseline_df is not None and entity_col in baseline_df.columns and DATE_COL in baseline_df.columns:
        bm = baseline_df.copy()
        if "_month" not in bm.columns:
            bm["_month"] = bm[DATE_COL].dt.to_period("M").astype(str)
        bm = bm[bm["_month"] == selected_month].copy()
        if not bm.empty:
            bm[entity_col] = bm[entity_col].fillna("").astype(str).str.strip()
            bm = bm[(bm[entity_col] != "") & (bm[entity_col].str.lower() != "nan")]
            entity_week_vals = []
            for ws, we in week_ranges:
                d_week = bm[(bm[DATE_COL] >= ws) & (bm[DATE_COL] <= we)]
                for _, d_ent in d_week.groupby(entity_col):
                    ov = compute_overall_from_aspects(d_ent, aspect_cols)
                    if not np.isnan(ov):
                        entity_week_vals.append(float(ov))
            if entity_week_vals:
                min_line = round(float(np.nanmin(entity_week_vals)), 2)
                max_line = round(float(np.nanmax(entity_week_vals)), 2)
                kkm_line = round(float(np.nanmean(entity_week_vals)), 2)

    valid_selected = [row["overall"] for row in weekly_sel if row.get("overall") is not None]
    if valid_selected:
        avg_selected = round(float(np.nanmean(valid_selected)), 2)

    daily_interest = []
    if actual_mask is not None:
        dfd = scope_df.copy()
        dfd["_day_dt"] = pd.to_datetime(dfd[DATE_COL]).dt.floor("D")
        dfd["_is_interest"] = actual_mask.reindex(dfd.index).fillna(False).astype(bool).values
        daily = dfd.groupby("_day_dt", as_index=False).agg(
            jumlah_minat=("_is_interest", "sum"), jumlah_rekaman=("_is_interest", "size"),
        )
        daily["rate_minat"] = np.nan
        valid = daily["jumlah_rekaman"] > 0
        daily.loc[valid, "rate_minat"] = (daily.loc[valid, "jumlah_minat"] / daily.loc[valid, "jumlah_rekaman"] * 100.0).round(2)
        for _, row in daily.sort_values("_day_dt").iterrows():
            daily_interest.append({
                "date": str(pd.Timestamp(row["_day_dt"]).date()),
                "minat": int(row["jumlah_minat"]),
                "rekaman": int(row["jumlah_rekaman"]),
                "rate": None if pd.isna(row["rate_minat"]) else float(row["rate_minat"]),
            })

    period_split = None
    if actual_mask is not None:
        period_info = split_calendar_month_ranges(yy, mm)
        period_split = {
            "label_1": period_info["label_1"],
            "label_2": period_info["label_2"],
            "period_1": build_daily_interest_for_period(scope_df, actual_mask, period_info["p1_start"], period_info["p1_end"]),
            "period_2": build_daily_interest_for_period(scope_df, actual_mask, period_info["p2_start"], period_info["p2_end"]),
        }

    rutin = None
    tidak_rutin = None
    if actual_mask is not None and entity_col == TL_COL:
        d = scope_df.copy()
        d["_day_dt"] = pd.to_datetime(d[DATE_COL]).dt.floor("D")
        active_days = sorted(d["_day_dt"].dropna().unique().tolist())
        if active_days:
            rutin_table = build_agent_daily_presence_summary(scope_df, actual_mask, active_days, allowed_missing_days=2, invert=False)
            tidak_rutin_table = build_agent_daily_presence_summary(scope_df, actual_mask, active_days, allowed_missing_days=2, invert=True)

            if rutin_table:
                rutin_agents = {row["agent"] for row in rutin_table}
                rutin = {
                    "table": rutin_table,
                    "daily": build_daily_interest_chart_for_agent_group(scope_df, actual_mask, rutin_agents),
                }
            if tidak_rutin_table:
                tidak_rutin_agents = {row["agent"] for row in tidak_rutin_table}
                tidak_rutin = {
                    "table": tidak_rutin_table,
                    "daily": build_daily_interest_chart_for_agent_group(scope_df, actual_mask, tidak_rutin_agents),
                }

    return {
        "weekly": weekly_sel,
        "min_line": min_line,
        "max_line": max_line,
        "kkm_line": kkm_line,
        "avg_selected": avg_selected,
        "daily_interest": daily_interest,
        "period_split": period_split,
        "rutin": rutin,
        "tidak_rutin": tidak_rutin,
    }


def build_hourly_trend(scope_df: pd.DataFrame, baseline_df: pd.DataFrame, aspect_cols: list[str], actual_mask=None, entity_col: str = TL_COL):
    dfh = scope_df.copy()
    if "_dt_call" not in dfh.columns:
        return {"overall": [], "interest": [], "not_interest": [], "call_mix": [], "duration": [], "reference_lines": {}}

    dfh = dfh.dropna(subset=["_dt_call"]).copy()
    if dfh.empty:
        return {"overall": [], "interest": [], "not_interest": [], "call_mix": [], "duration": [], "reference_lines": {}}

    dfh["_hour"] = dfh["_dt_call"].dt.hour
    display_hours = get_display_hours(dfh)
    sort_labels = [f"{h:02d}:00" for h in display_hours]

    overall_rows = []
    for h in display_hours:
        d = dfh[dfh["_hour"] == h]
        rekaman = int(len(d))
        overall = None
        if not d.empty:
            ov = compute_overall_from_aspects(d, aspect_cols)
            overall = None if np.isnan(ov) else float(ov)
        overall_rows.append({
            "jam": f"{h:02d}:00",
            "hour": h,
            "rekaman": rekaman,
            "overall": overall,
        })

    valid_overall = [row["overall"] for row in overall_rows if row.get("overall") is not None]
    avg_selected = round(float(np.nanmean(valid_overall)), 2) if valid_overall else None

    ref_lines = compute_hourly_reference_lines(baseline_df, aspect_cols, entity_col, display_hours)
    ref_lines["avg_selected"] = avg_selected
    ref_lines["reference_basis"] = "Seluruh TL" if entity_col == TL_COL else "Agent pada TL ini"

    interest_rows = []
    not_interest_rows = []
    if actual_mask is not None:
        df_interest = dfh.copy()
        df_interest["_is_interest"] = actual_mask.reindex(df_interest.index).fillna(False).astype(bool).values
        df_interest["_is_not_interest"] = ~df_interest["_is_interest"]

        for h in display_hours:
            d = df_interest[df_interest["_hour"] == h]
            total = int(len(d))
            minat = int(d["_is_interest"].sum()) if total > 0 else 0
            tidak_minat = int(d["_is_not_interest"].sum()) if total > 0 else 0
            rate_minat = round(minat / total * 100.0, 2) if total > 0 else None
            rate_tidak_minat = round(tidak_minat / total * 100.0, 2) if total > 0 else None
            interest_rows.append({
                "jam": f"{h:02d}:00",
                "hour": h,
                "rekaman": total,
                "count": minat,
                "rate": rate_minat,
            })
            not_interest_rows.append({
                "jam": f"{h:02d}:00",
                "hour": h,
                "rekaman": total,
                "count": tidak_minat,
                "rate": rate_tidak_minat,
            })

    call_mix_rows = []
    if CALLRESULT_COL in dfh.columns:
        df_call = dfh.copy()
        df_call["_call_group"] = df_call[CALLRESULT_COL].apply(normalize_call_group)
        for h in display_hours:
            d = df_call[df_call["_hour"] == h]
            call_mix_rows.append({
                "jam": f"{h:02d}:00",
                "hour": h,
                "minat": int((d["_call_group"] == "Minat").sum()),
                "tidak_minat": int((d["_call_group"] == "Tidak Minat").sum()),
                "appointment": int((d["_call_group"] == "Appointment").sum()),
                "rekaman": int(len(d)),
            })

    duration_rows = []
    if DURATION_COL in dfh.columns:
        dfd = dfh.copy()
        dfd["_duration_sec"] = dfd[DURATION_COL].apply(parse_duration_seconds)
        for h in display_hours:
            d = dfd[dfd["_hour"] == h].dropna(subset=["_duration_sec"])
            if d.empty:
                duration_rows.append({"jam": f"{h:02d}:00", "hour": h, "avg_sec": None, "avg_mmss": None, "count": 0})
                continue
            avg_sec = float(d["_duration_sec"].mean())
            duration_rows.append({
                "jam": f"{h:02d}:00",
                "hour": h,
                "avg_sec": round(avg_sec, 2),
                "avg_mmss": format_seconds_mmss(avg_sec),
                "count": int(len(d)),
            })

    return {
        "sort_labels": sort_labels,
        "display_hours": display_hours,
        "overall": overall_rows,
        "interest": interest_rows,
        "not_interest": not_interest_rows,
        "call_mix": call_mix_rows,
        "duration": duration_rows,
        "reference_lines": ref_lines,
    }


def get_detail_agent(scope_df: pd.DataFrame, agent_name: str):
    d = scope_df.copy()
    d[AGENT_COL] = d[AGENT_COL].fillna("").astype(str).str.strip()
    d = d[d[AGENT_COL] == agent_name]
    aspect_cols = [c for c in ASPECT_COLUMNS_CANDIDATES if c in d.columns]
    records = []
    for _, row in d.iterrows():
        rec = {
            "tanggal": str(row.get(DATETIME_COL, "")),
            "call_result": str(row.get(CALLRESULT_COL, "")),
            "agent": str(row.get(AGENT_COL, "")),
        }
        for col in aspect_cols:
            rec[ASPECT_FRIENDLY_NAMES.get(col, col)] = normalize_to_binary(row[col])
        records.append(rec)
    return {"agent": agent_name, "total": len(records), "records": records}


# =========================
# SCOPE + PAYLOAD BUILDERS
# =========================
def _month_list_from_df(df: pd.DataFrame) -> list[str]:
    if DATE_COL not in df.columns:
        return []
    months = df[DATE_COL].dropna().dt.to_period("M").astype(str).drop_duplicates().tolist()
    return sorted(months)


def prepare_scope(df: pd.DataFrame, params: ProcessParams) -> dict:
    mode = (params.mode or "Agent").strip()
    if mode not in {"Agent", "TL"}:
        raise ValueError("mode harus 'Agent' atau 'TL'.")
    if not params.selected_tl:
        raise ValueError("selected_tl wajib diisi.")
    if TL_COL not in df.columns:
        raise ValueError(f"Kolom '{TL_COL}' tidak ditemukan.")
    if AGENT_COL not in df.columns:
        raise ValueError(f"Kolom '{AGENT_COL}' tidak ditemukan.")

    allowed = params.allowed_call_types or DEFAULT_ALLOWED_CALL_TYPES

    # Mirror app.py behavior more closely: normalize string identity values first,
    # but do not globally drop rows except where needed for meta/sidebar.
    raw = normalize_identity_values(df)

    # Agent mode in app.py scopes baseline to all rows under selected TL.
    df_tl_all = raw[raw[TL_COL] == params.selected_tl].copy()
    if df_tl_all.empty:
        raise ValueError("Tidak ada data untuk Team Leader tersebut.")

    if mode == "Agent":
        if not params.selected_agent:
            raise ValueError("selected_agent wajib untuk mode Agent.")
        df_sel = df_tl_all[df_tl_all[AGENT_COL] == params.selected_agent].copy()
        baseline_df = df_tl_all.copy()
        entity_col = AGENT_COL
    else:
        df_sel = df_tl_all.copy()
        df_all_tl = raw.copy()
        df_all_tl = df_all_tl[(df_all_tl[TL_COL] != "") & (df_all_tl[TL_COL].str.lower() != "nan")].copy()
        baseline_df = df_all_tl
        entity_col = TL_COL

    if df_sel.empty:
        raise ValueError("Tidak ada data untuk filter ini.")

    df_base = filter_call_types(df_sel, allowed)
    if df_base.empty:
        raise ValueError("Tidak ada data setelah filter call type.")

    df_base = ensure_date_and_dt(df_base)
    baseline_df = ensure_date_and_dt(filter_call_types(baseline_df, allowed))

    unique_days = int(df_base[DATE_COL].dt.date.nunique())
    time_mode = "Harian" if unique_days <= 1 else "Bulanan"

    month_list: list[str] = []
    selected_month = params.selected_month
    if time_mode == "Bulanan":
        df_base["_month"] = df_base[DATE_COL].dt.to_period("M").astype(str)
        month_list = sorted(df_base["_month"].dropna().unique().tolist())
        if not month_list:
            raise ValueError("Data tanggal bulanan tidak valid.")
        if not selected_month or selected_month not in month_list:
            selected_month = month_list[-1]
        scope_df = df_base[df_base["_month"] == selected_month].copy()
    else:
        scope_df = df_base.copy()
        only_day = df_base[DATE_COL].dt.date.dropna().unique()
        selected_month = str(only_day[0]) if len(only_day) else "-"

    if scope_df.empty:
        raise ValueError("Tidak ada data pada periode terpilih.")

    if time_mode == "Bulanan":
        baseline_df["_month"] = baseline_df[DATE_COL].dt.to_period("M").astype(str)

    aspect_cols = [c for c in ASPECT_COLUMNS_CANDIDATES if c in scope_df.columns]
    return {
        "mode": mode,
        "allowed": allowed,
        "scope_df": scope_df,
        "baseline_df": baseline_df,
        "time_mode": time_mode,
        "selected_month": selected_month,
        "month_list": month_list,
        "aspect_cols": aspect_cols,
        "entity_col": entity_col,
        "df_tl": df_tl_all,
    }


def build_dashboard_payload(df: pd.DataFrame, params: ProcessParams) -> dict:
    scoped = prepare_scope(df, params)
    scope_df = scoped["scope_df"]
    baseline_df = scoped["baseline_df"]
    time_mode = scoped["time_mode"]
    selected_month = scoped["selected_month"]
    month_list = scoped["month_list"]
    aspect_cols = scoped["aspect_cols"]
    entity_col = scoped["entity_col"]

    im = interest_masks(scope_df)
    interest_kpi = {}
    actual_mask = None
    if im is not None:
        actual_mask = im["actual_mask"]
        if im["mode"] == "lov3":
            interest_kpi = {
                "mode": "lov3",
                "warm_leads": int(im["ai_mask"].sum()),
                "tidak_minat": int((~im["ai_mask"]).sum()),
            }
        else:
            interest_kpi = {
                "mode": "sentiment",
                "ai_minat": int(im["ai_mask"].sum()),
                "agent_minat": int(im["agent_mask"].sum()),
                "aktual_minat": int(im["actual_mask"].sum()),
            }

    result_table = build_result_table(scope_df, time_mode, selected_month if time_mode == "Bulanan" else None)
    daily_aspect_breakdown = build_daily_aspect_agent_breakdown(scope_df, result_table.get("rows", [])) if time_mode == "Harian" else {}

    agent_comparison = None
    if params.mode == "TL":
        worst, best = build_tl_agent_comparison(scope_df, aspect_cols)
        if worst and best:
            agent_comparison = {"worst": worst[:10], "best": best[:10]}

    agent_interest_summary = build_agent_interest_summary(scope_df) if params.mode == "TL" else None
    priority_t1, priority_t2 = build_priority_followup_tables(scope_df)
    weekly_trend = None
    if time_mode == "Bulanan":
        weekly_trend = build_weekly_trend(scope_df, baseline_df, selected_month, aspect_cols, entity_col, actual_mask)
    hourly_trend = build_hourly_trend(scope_df, baseline_df, aspect_cols, actual_mask, entity_col)

    agent_count = None
    if params.mode == "TL":
        agent_count = int(scope_df[AGENT_COL].fillna("").astype(str).str.strip().replace("nan", "").replace("", np.nan).dropna().nunique())

    overall = result_table.get("overall") if isinstance(result_table, dict) else None
    total_rekaman = int(len(scope_df))

    return {
        "mode": params.mode,
        "time_mode": time_mode,
        "selected_tl": params.selected_tl,
        "selected_agent": params.selected_agent,
        "selected_month": selected_month,
        "month_list": month_list,
        "overall": overall,
        "total_rekaman": total_rekaman,
        "aspect_count": len(aspect_cols),
        "agent_count": agent_count,
        "interest_kpi": make_json_safe(interest_kpi),
        "result_table": make_json_safe(result_table),
        "agent_comparison": make_json_safe(agent_comparison),
        "agent_interest_summary": make_json_safe(agent_interest_summary),
        "priority_t1": make_json_safe(priority_t1),
        "priority_t2": make_json_safe(priority_t2),
        "weekly_trend": make_json_safe(weekly_trend),
        "hourly_trend": make_json_safe(hourly_trend),
        "daily_aspect_breakdown": make_json_safe(daily_aspect_breakdown),
    }



def build_priority_agent_detail_payload(df: pd.DataFrame, params: ProcessParams, table_type: str, agent: str) -> dict:
    scoped = prepare_scope(df, params)
    records = _priority_table_records(scoped["scope_df"], table_type)
    selected_agent = (agent or "").strip()
    filtered = [rec for rec in records if str(rec.get("agent", "")).strip() == selected_agent]
    filtered = sorted(filtered, key=lambda x: str(x.get("tanggal", "")), reverse=True)

    title = (
        "Detail Call Minat: Agent Jarang Menyebut 3 Aspek Prioritas"
        if table_type == "t1"
        else "Detail Call Tidak Minat: Agent Sudah Simulasi (Potensi Follow Up)"
    )

    return {
        "agent": selected_agent,
        "table_type": table_type,
        "title": title,
        "total": len(filtered),
        "records": filtered[:200],
    }


def build_detail_agent_payload(df: pd.DataFrame, tl: str, agent: str, month: Optional[str] = None) -> dict:
    params = ProcessParams(mode="Agent", selected_tl=tl, selected_agent=agent, selected_month=month)
    scoped = prepare_scope(df, params)
    return make_json_safe(get_detail_agent(scoped["scope_df"], agent))
