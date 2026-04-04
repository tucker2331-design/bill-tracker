import io
import json
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

st.set_page_config(page_title="LIS Calendar X-Ray", layout="wide")
st.title("🩻 LIS Calendar X-Ray")
st.caption("Diagnostic tool for Sheet1 ↔ LIS schedule parity checks.")
XRAY_VERSION = "2026-04-04.1"
st.caption(f"Build: {XRAY_VERSION}")

DEFAULT_SHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
DEFAULT_SESSION_CODE = "261"
DEFAULT_API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"

PLACEHOLDER_TIMES = {"", "nan", "none", "time tba", "journal entry", "ledger"}
NON_CONCRETE_LIS_TIMES = {"", "none", "nan", "tba", "time tba"}

# Diagnostic tag patterns injected by calendar_worker.py
TAG_PATTERNS = {
    "PARENT_CHILD": "PARENT_CHILD",
    "TIMING_LAG": "TIMING_LAG",
    "COMMITTEE_DRIFT": "COMMITTEE_DRIFT",
    "UNKNOWN_ACTION": "UNKNOWN_ACTION",
    "Memory Anchor": "Memory Anchor",
}


def get_http_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0 Codex-LIS-Xray"})
    return session


def normalize_committee(text: str) -> str:
    cleaned = str(text or "").lower().strip()
    for token in ["committee", "on", "for", "the", "of", "and", "&", ",", ".", "-"]:
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def normalize_time(value: str) -> str:
    return str(value or "").strip().lower()


def load_sheet_df(http: requests.Session, sheet_id: str) -> tuple[pd.DataFrame, str]:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Sheet1"
    res = http.get(url, timeout=15)
    res.raise_for_status()
    return pd.read_csv(io.StringIO(res.text)), url


def load_lis_schedule(http: requests.Session, session_code: str, api_key: str) -> tuple[pd.DataFrame, str]:
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": api_key, "Accept": "application/json"}
    res = http.get(url, headers=headers, params={"sessionCode": session_code}, timeout=20)
    res.raise_for_status()
    payload = res.json()
    rows = payload.get("Schedules", []) if isinstance(payload, dict) else payload
    return pd.DataFrame(rows), res.url


def parse_uploaded_lis(file_obj) -> pd.DataFrame:
    if file_obj is None:
        return pd.DataFrame()
    content = file_obj.getvalue().decode("utf-8", errors="replace")
    if file_obj.name.lower().endswith(".json"):
        payload = json.loads(content)
        rows = payload.get("Schedules", []) if isinstance(payload, dict) else payload
        return pd.DataFrame(rows)
    return pd.read_csv(io.StringIO(content))


def compute_missing_time_diagnostics(sheet_df: pd.DataFrame) -> pd.DataFrame:
    df = sheet_df.copy()
    for col in ["Date", "Committee", "Time", "SortTime", "Bill", "Outcome", "Source", "Status"]:
        if col not in df.columns:
            df[col] = ""

    missing_mask = df["Time"].map(normalize_time).isin(PLACEHOLDER_TIMES)
    out = df.loc[missing_mask].copy()
    out["missing_reason"] = out["Time"].map(lambda x: f"placeholder:{normalize_time(x)}")
    return out


def build_lis_committee_time_map(lis_df: pd.DataFrame) -> pd.DataFrame:
    if lis_df.empty:
        return pd.DataFrame(columns=["Date", "LIS_Committee", "LIS_Time", "norm_key"])

    date_col = "ScheduleDate" if "ScheduleDate" in lis_df.columns else None
    owner_col = "OwnerName" if "OwnerName" in lis_df.columns else None
    time_col = "ScheduleTime" if "ScheduleTime" in lis_df.columns else None

    if not all([date_col, owner_col, time_col]):
        return pd.DataFrame(columns=["Date", "LIS_Committee", "LIS_Time", "norm_key"])

    out = pd.DataFrame(
        {
            "Date": pd.to_datetime(lis_df[date_col], errors="coerce").dt.strftime("%Y-%m-%d"),
            "LIS_Committee": lis_df[owner_col].astype(str),
            "LIS_Time": lis_df[time_col].astype(str).str.strip(),
        }
    )
    out["norm_key"] = out["LIS_Committee"].map(normalize_committee)
    out = out.dropna(subset=["Date"])
    out = out[out["LIS_Committee"].str.len() > 0]
    out = out.drop_duplicates(subset=["Date", "norm_key", "LIS_Time"])
    return out


def classify_join_gaps(joined: pd.DataFrame) -> pd.DataFrame:
    out = joined.copy()
    out["gap_type"] = "missing_sheet_time"
    out.loc[out["Date"].isna(), "gap_type"] = "bad_sheet_date"
    out.loc[out["norm_key"].eq(""), "gap_type"] = "bad_sheet_committee"
    out.loc[out["LIS_Committee"].isna(), "gap_type"] = "no_lis_committee_match"

    lis_non_concrete = out["LIS_Time"].map(normalize_time).isin(NON_CONCRETE_LIS_TIMES)
    out.loc[~out["LIS_Committee"].isna() & lis_non_concrete, "gap_type"] = "lis_time_not_concrete"
    out.loc[~out["LIS_Committee"].isna() & ~lis_non_concrete, "gap_type"] = "sheet_missing_lis_has_time"
    return out


def count_diagnostic_tags(sheet_df: pd.DataFrame) -> dict:
    """Count diagnostic tags injected by calendar_worker into Outcome column."""
    if "Outcome" not in sheet_df.columns:
        return {}
    outcomes = sheet_df["Outcome"].astype(str)
    counts = {}
    for label, pattern in TAG_PATTERNS.items():
        counts[label] = int(outcomes.str.contains(pattern, na=False).sum())
    return counts


# ===================== SIDEBAR =====================
with st.sidebar:
    st.header("Run Mode")
    mode = st.radio("Data source", ["Live fetch", "Manual upload"], index=0)

    st.header("Live Inputs")
    sheet_id = st.text_input("Google Sheet ID", value=DEFAULT_SHEET_ID)
    session_code = st.text_input("LIS Session Code", value=DEFAULT_SESSION_CODE)
    api_key = st.text_input("LIS WebAPIKey", value=DEFAULT_API_KEY, type="password")

    st.header("Manual Inputs")
    st.caption("Use this if your environment blocks Google/LIS outbound traffic.")
    sheet_upload = st.file_uploader("Upload Sheet1 CSV", type=["csv"], accept_multiple_files=False)
    lis_upload = st.file_uploader("Upload LIS schedule JSON/CSV", type=["json", "csv"], accept_multiple_files=False)

    run = st.button("Run X-Ray")

if not run:
    st.info("Choose mode, provide inputs, and click **Run X-Ray**.")
    st.stop()

sheet_df = pd.DataFrame()
sheet_ref = ""
lis_df = pd.DataFrame()
lis_ref = ""

c1, c2 = st.columns(2)

if mode == "Live fetch":
    http = get_http_session()

    with c1:
        st.subheader("1) Sheet1 Connectivity")
        try:
            sheet_df, sheet_ref = load_sheet_df(http, sheet_id)
            st.success(f"Loaded Sheet1 rows: {len(sheet_df)}")
            st.code(sheet_ref)
        except requests.RequestException as exc:
            st.error(f"Failed to load Sheet1 (network/http): {exc}")
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            st.error(f"Failed to parse Sheet1 CSV: {exc}")

    with c2:
        st.subheader("2) LIS Schedule Connectivity")
        try:
            lis_df, lis_ref = load_lis_schedule(http, session_code, api_key)
            st.success(f"Loaded LIS schedule rows: {len(lis_df)}")
            st.code(lis_ref)
        except requests.RequestException as exc:
            st.error(f"Failed to load LIS schedule (network/http): {exc}")
        except json.JSONDecodeError as exc:
            st.error(f"Failed to decode LIS JSON payload: {exc}")
else:
    with c1:
        st.subheader("1) Sheet1 Upload")
        if sheet_upload is None:
            st.warning("Please upload a Sheet1 CSV file.")
        else:
            try:
                sheet_df = pd.read_csv(io.StringIO(sheet_upload.getvalue().decode("utf-8", errors="replace")))
                sheet_ref = sheet_upload.name
                st.success(f"Loaded Sheet rows: {len(sheet_df)}")
            except pd.errors.ParserError as exc:
                st.error(f"Invalid Sheet CSV: {exc}")

    with c2:
        st.subheader("2) LIS Upload")
        if lis_upload is None:
            st.warning("Please upload LIS schedule JSON or CSV.")
        else:
            try:
                lis_df = parse_uploaded_lis(lis_upload)
                lis_ref = lis_upload.name
                st.success(f"Loaded LIS rows: {len(lis_df)}")
            except (json.JSONDecodeError, pd.errors.ParserError, UnicodeDecodeError) as exc:
                st.error(f"Invalid LIS upload: {exc}")

if sheet_df.empty:
    st.warning("Sheet data unavailable; cannot audit.")
    st.stop()

# ===================== SECTION 3: EXECUTIVE SUMMARY =====================
st.divider()
st.subheader("3) Executive Summary")

total_rows = len(sheet_df)
source_counts = sheet_df["Source"].value_counts().to_dict() if "Source" in sheet_df.columns else {}
csv_rows = source_counts.get("CSV", 0)
api_rows = sum(v for k, v in source_counts.items() if str(k).startswith("API"))
docket_rows = source_counts.get("DOCKET", 0)
system_rows = source_counts.get("SYSTEM", 0)
ledger_rows = int((sheet_df.get("Committee", pd.Series()) == "📋 Ledger Updates").sum())

tag_counts = count_diagnostic_tags(sheet_df)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Rows", f"{total_rows:,}")
col2.metric("CSV (History)", f"{csv_rows:,}")
col3.metric("API/Docket", f"{api_rows + docket_rows:,}")
col4.metric("Ledger Updates", f"{ledger_rows:,}")

col5, col6, col7, col8 = st.columns(4)
col5.metric("🏷 PARENT_CHILD", tag_counts.get("PARENT_CHILD", 0))
col6.metric("🏷 TIMING_LAG", tag_counts.get("TIMING_LAG", 0))
col7.metric("🏷 COMMITTEE_DRIFT", tag_counts.get("COMMITTEE_DRIFT", 0))
col8.metric("🏷 UNKNOWN_ACTION", tag_counts.get("UNKNOWN_ACTION", 0))

col9, col10, col11, col12 = st.columns(4)
col9.metric("⚙️ Memory Anchor", tag_counts.get("Memory Anchor", 0))
col10.metric("🔔 System Alerts", system_rows)
col11.metric("Source: API", api_rows)
col12.metric("Source: DOCKET", docket_rows)


# ===================== SECTION 4: MISSING TIME AUDIT =====================
st.divider()
st.subheader("4) Missing/Placeholder Time Audit")

missing_df = compute_missing_time_diagnostics(sheet_df)
st.metric("Sheet rows with placeholder/missing time", len(missing_df))

if not missing_df.empty:
    # --- 4a: Breakdown by committee ---
    st.markdown("#### 4a) Placeholder Rows by Committee")
    by_committee = (
        missing_df.groupby("Committee")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    st.dataframe(by_committee, use_container_width=True, hide_index=True)

    # --- 4b: Breakdown by date ---
    st.markdown("#### 4b) Placeholder Rows by Date")
    by_date = (
        missing_df.groupby("Date")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    st.dataframe(by_date, use_container_width=True, hide_index=True)

    # --- 4c: Breakdown by missing_reason ---
    st.markdown("#### 4c) Placeholder Rows by Reason")
    by_reason = (
        missing_df.groupby("missing_reason")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )
    st.dataframe(by_reason, use_container_width=True, hide_index=True)

    # --- 4d: Sample rows (capped) ---
    st.markdown("#### 4d) Sample Rows")
    st.dataframe(
        missing_df[["Date", "Committee", "Time", "SortTime", "Source", "Bill", "Outcome", "missing_reason"]].head(200),
        use_container_width=True,
        hide_index=True,
    )


# ===================== SECTION 5: DIAGNOSTIC TAG DEEP DIVE =====================
st.divider()
st.subheader("5) Diagnostic Tag Deep Dive")

if "Outcome" in sheet_df.columns:
    for tag_label, tag_pattern in TAG_PATTERNS.items():
        tag_mask = sheet_df["Outcome"].astype(str).str.contains(tag_pattern, na=False)
        tag_count = int(tag_mask.sum())
        if tag_count > 0:
            with st.expander(f"🏷 {tag_label} ({tag_count} rows)", expanded=False):
                tag_rows = sheet_df.loc[tag_mask, ["Date", "Committee", "Time", "Bill", "Outcome"]].head(100)
                st.dataframe(tag_rows, use_container_width=True, hide_index=True)
else:
    st.info("No Outcome column found in Sheet1.")


# ===================== SECTION 6: TIMED ROWS AUDIT =====================
st.divider()
st.subheader("6) Timed Rows Audit (Rows WITH Concrete Times)")

if "Time" in sheet_df.columns:
    timed_mask = ~sheet_df["Time"].map(normalize_time).isin(PLACEHOLDER_TIMES)
    timed_df = sheet_df.loc[timed_mask]
    st.metric("Rows with concrete times", len(timed_df))

    if not timed_df.empty:
        timed_by_committee = (
            timed_df.groupby("Committee")
            .size()
            .reset_index(name="timed_count")
            .sort_values("timed_count", ascending=False)
        )
        st.dataframe(timed_by_committee.head(30), use_container_width=True, hide_index=True)


# ===================== SECTION 7: LIS PARITY CHECK =====================
st.divider()
st.subheader("7) Compare Missing-Time Rows against LIS Schedule")

if lis_df.empty:
    st.warning("LIS schedule unavailable; cannot produce parity diff.")
else:
    lis_map = build_lis_committee_time_map(lis_df)
    if lis_map.empty:
        st.error("Could not build LIS map. Ensure LIS payload includes ScheduleDate, OwnerName, and ScheduleTime.")
    elif missing_df.empty:
        st.success("No missing-time rows to compare against LIS.")
    else:
        work = missing_df.copy()
        work["Date"] = pd.to_datetime(work["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
        work["norm_key"] = work["Committee"].astype(str).map(normalize_committee)

        joined = work.merge(
            lis_map[["Date", "norm_key", "LIS_Committee", "LIS_Time"]],
            on=["Date", "norm_key"],
            how="left",
        )

        classified = classify_join_gaps(joined)

        issues = classified[classified["gap_type"] == "sheet_missing_lis_has_time"].copy()
        st.metric("🚨 Rows missing time in Sheet but WITH time in LIS", len(issues))

        if issues.empty:
            st.success("No direct committee/date matches found where LIS had a concrete time.")
        else:
            st.dataframe(
                issues[["Date", "Committee", "Time", "Source", "Bill", "LIS_Committee", "LIS_Time", "Outcome"]].head(700),
                use_container_width=True,
                hide_index=True,
            )

        # --- Gap breakdown ---
        st.markdown("#### Gap Breakdown")
        gap_counts = classified["gap_type"].value_counts().rename_axis("gap_type").reset_index(name="count")
        st.dataframe(gap_counts, use_container_width=True, hide_index=True)

        # --- no_lis_committee_match deep dive ---
        no_match = classified[classified["gap_type"] == "no_lis_committee_match"]
        if not no_match.empty:
            st.markdown("#### No-LIS-Committee-Match by Committee Name")
            no_match_by_comm = (
                no_match.groupby("Committee")
                .size()
                .reset_index(name="count")
                .sort_values("count", ascending=False)
            )
            st.dataframe(no_match_by_comm, use_container_width=True, hide_index=True)


# ===================== SECTION 8: SYSTEM ALERTS =====================
st.divider()
st.subheader("8) System Alerts")

if "Source" in sheet_df.columns:
    system_df = sheet_df[sheet_df["Source"] == "SYSTEM"]
    if system_df.empty:
        st.success("No system alerts in current build.")
    else:
        st.warning(f"{len(system_df)} system alert(s) found:")
        st.dataframe(
            system_df[["Date", "Time", "Status", "Outcome"]],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("No Source column found.")


# ===================== SECTION 9: DOWNLOAD =====================
st.divider()
st.subheader("9) Download Payload")

gap_counts_data = []
if lis_df is not None and not lis_df.empty and not missing_df.empty:
    gap_counts_data = gap_counts.to_dict(orient="records") if "gap_counts" in dir() else []

payload = {
    "generated_at_utc": datetime.utcnow().isoformat() + "Z",
    "xray_version": XRAY_VERSION,
    "mode": mode,
    "sheet_ref": sheet_ref,
    "lis_ref": lis_ref,
    "sheet_rows": int(len(sheet_df)),
    "missing_rows": int(len(missing_df)) if not missing_df.empty else 0,
    "lis_rows": int(len(lis_df)),
    "issues_rows": int(len(issues)) if "issues" in dir() else 0,
    "tag_counts": tag_counts,
    "source_counts": {str(k): int(v) for k, v in source_counts.items()},
    "gap_counts": gap_counts_data,
}
st.download_button("Download summary JSON", data=json.dumps(payload, indent=2), file_name="xray_summary.json")
