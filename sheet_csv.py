"""Read a tab of the project spreadsheet as gviz CSV — with a read-only service-account token when one is configured.

WHY (owner, 2026-09-28): the whole product goes private. The web app now reads through the Worker's gated
/api/sheet (worker/sheets.js); once that is live the spreadsheet's link-sharing is turned OFF. The internal
Streamlit pages (X-Ray, the calendar entry page) read the same sheet over public gviz and would break at that
moment — or, worse, keep the sheet public so they keep working. This helper keeps the EXACT same CSV (so every
downstream pd.read_csv behaves identically) and adds an OAuth bearer token when credentials exist.

Credentials, first found wins: env GCP_CREDENTIALS (the JSON the workers already use), then Streamlit secret
GCP_CREDENTIALS (a JSON string or a TOML table). None -> an unauthenticated read, which works only while the
sheet is link-shared; the mode is RETURNED so callers can show it, never hidden.

A private sheet read without a token answers 200 with Google's HTML sign-in page. That is detected by content
type and raised as an error — it must never reach a CSV parser as "a sheet with one weird column".
"""
from __future__ import annotations

import json
import os

import requests

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


def _credential_info():
    raw = os.environ.get("GCP_CREDENTIALS")
    if raw:
        return json.loads(raw)
    try:
        import streamlit as st  # optional: only the Streamlit pages have it
        sec = st.secrets.get("GCP_CREDENTIALS")
    except Exception as e:  # noqa: BLE001 -- no Streamlit / no secrets file is a normal "no credentials" case
        print(f"ℹ️  sheet_csv: no Streamlit secrets ({type(e).__name__}); reading without a token.")
        return None
    if not sec:
        return None
    return json.loads(sec) if isinstance(sec, str) else dict(sec)


def _token():
    info = _credential_info()
    if not info:
        return None
    from google.oauth2.service_account import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    creds.refresh(Request())
    return creds.token


def fetch_sheet_csv(sheet_id: str, tab: str, http: requests.Session | None = None, timeout: int = 20):
    """-> (csv_text, url, auth_mode) where auth_mode is "service_account" or "none". Raises on a non-CSV answer."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(tab)}"
    token = _token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    res = (http or requests).get(url, headers=headers, timeout=timeout)
    res.raise_for_status()
    ctype = res.headers.get("content-type", "")
    if "text/csv" not in ctype:
        raise RuntimeError(f"sheet {tab!r} did not return CSV (content-type {ctype!r}, auth "
                           f"{'service_account' if token else 'none'}) -- a private sheet needs GCP_CREDENTIALS")
    return res.text, url, "service_account" if token else "none"
