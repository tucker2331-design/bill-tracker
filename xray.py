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
XRAY_VERSION = "2026-04-03.4"
st.caption(f"Build: {XRAY_VERSION}")

DEFAULT_SHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
DEFAULT_SESSION_CODE = "261"
DEFAULT_API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"

PLACEHOLDER_TIMES = {"", "nan", "none", "time tba", "journal entry", "ledger"}
NON_CONCRETE_LIS_TIMES = {"", "none", "nan", "tba", "time tba"}


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

st.divider()
st.subheader("3) Missing/Placeholder Time Audit")

if sheet_df.empty:
    st.warning("Sheet data unavailable; cannot audit missing times.")
    st.stop()

missing_df = compute_missing_time_diagnostics(sheet_df)
st.metric("Sheet rows with placeholder/missing time", len(missing_df))

if missing_df.empty:
    st.success("No placeholder/missing time rows found in Sheet1.")
    st.stop()

st.dataframe(
    missing_df[["Date", "Committee", "Time", "SortTime", "Source", "Bill", "Outcome", "missing_reason"]].head(500),
    use_container_width=True,
    hide_index=True,
)

st.subheader("4) Compare Missing-Time Rows against LIS Schedule")
if lis_df.empty:
    st.warning("LIS schedule unavailable; cannot produce parity diff.")
    st.stop()

lis_map = build_lis_committee_time_map(lis_df)
if lis_map.empty:
    st.error("Could not build LIS map. Ensure LIS payload includes ScheduleDate, OwnerName, and ScheduleTime.")
    st.stop()

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
st.metric("Rows missing time in Sheet but with time in LIS", len(issues))

if issues.empty:
    st.info("No direct committee/date matches found where LIS had a concrete time.")
else:
    st.dataframe(
        issues[["Date", "Committee", "Time", "Source", "Bill", "LIS_Committee", "LIS_Time", "Outcome"]].head(700),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("5) Gap Breakdown")
gap_counts = classified["gap_type"].value_counts().rename_axis("gap_type").reset_index(name="count")
st.dataframe(gap_counts, use_container_width=True, hide_index=True)

st.subheader("6) Download Payload")
payload = {
    "generated_at_utc": datetime.utcnow().isoformat() + "Z",
    "mode": mode,
    "sheet_ref": sheet_ref,
    "lis_ref": lis_ref,
    "sheet_rows": int(len(sheet_df)),
    "missing_rows": int(len(missing_df)),
    "lis_rows": int(len(lis_df)),
    "issues_rows": int(len(issues)),
    "gap_counts": gap_counts.to_dict(orient="records"),
}
st.download_button("Download summary JSON", data=json.dumps(payload, indent=2), file_name="xray_summary.json")
