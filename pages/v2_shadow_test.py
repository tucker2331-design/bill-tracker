import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime
import json
import gspread

st.set_page_config(page_title="Integration Test", layout="wide")
st.title("🔌 Step 3.5: HB1 Database Integration Test")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"
LIS_HISTORY_CSV = "https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV"
LIS_DOCKET_CSV = "https://lis.blob.core.windows.net/lisfiles/20261/DOCKET.CSV"
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"

# --- REQUIRED ENGINE FUNCTIONS ---
def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    return re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)

if st.button("🚀 Write HB1 to Google Sheets"):
    with st.spinner("1. Authenticating..."):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1
        except Exception as e:
            st.error(f"❌ Auth Failed: {e}"); st.stop()

    with st.spinner("2. Processing HB1 Data..."):
        # API & CSV Pull
        api_data = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": "20261"}).json()
        hb1_data = next((b for b in api_data.get("Legislations", []) if b.get("LegislationNumber") == "HB1"), None)
        
        hist_df = pd.read_csv(LIS_HISTORY_CSV, encoding='ISO-8859-1', on_bad_lines='skip')
        hist_df.columns = hist_df.columns.str.strip().str.lower().str.replace(' ', '_')
        hist_col = next((c for c in hist_df.columns if c in ['bill_number','bill_id','bill_no']), None)
        hist_df['bill_clean'] = hist_df[hist_col].astype(str).apply(clean_bill_id) if hist_col else ""
        hb1_history = hist_df[hist_df['bill_clean'] == 'HB1'].to_dict('records')

        # Formatting History
        history_data = []
        for h_row in hb1_history:
            desc = next((str(h_row[c]) for c in ['history_description', 'description', 'action'] if c in h_row and pd.notna(h_row[c])), "")
            date_h = next((str(h_row[c]) for c in ['history_date', 'date'] if c in h_row and pd.notna(h_row[c])), "")
            if desc: history_data.append({"Date": date_h, "Action": desc})

        # The 12-Column Payload (Hardcoded logic variables for the quick test)
        sheet_data = [
            ["Bill Number", "Official Title", "Status", "Date", "Lifecycle", "Auto_Folder", "Is_Youth", "Current_Committee", "Display_Committee", "Current_Sub", "History_Data", "Upcoming_Meetings"],
            [
                "HB1", 
                hb1_data.get("Description", "No Title"), 
                hb1_data.get("LegislationStatus", "Unknown"), 
                "3/11/2026", 
                "✍️ Awaiting Signature", 
                "✊ Labor & Workers Rights", 
                "FALSE", 
                "Unassigned", 
                "📜 On Floor / Chamber Action", 
                "-", 
                json.dumps(history_data), # Testing the Stringification!
                "[]"
            ]
        ]

    with st.spinner("3. Blasting to Database..."):
        worksheet.clear()
        worksheet.update(values=sheet_data, range_name="A1")
        st.success("✅ HB1 Integration Test Complete! Go check your Google Sheet!")
