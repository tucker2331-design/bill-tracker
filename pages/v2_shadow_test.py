import streamlit as st
import requests
import gspread

st.set_page_config(page_title="Phase 2: Database Bridge", layout="wide")
st.title("🏗️ Phase 2: Mastermind Database Bridge")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {
    "WebAPIKey": API_KEY, 
    "Accept": "application/json"
}
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"

# ⚠️ Architect: Your Google Sheet ID is locked in!
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"

st.markdown("This script pulls the universal JSON data, grabs the raw list, and uses the `tracker-bot` to write it directly to your Sheet.")

if st.button("🔥 Execute Database Bridge (Write to Sheets)"):
    with st.spinner("1. Authenticating with Google Cloud Vault..."):
        try:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.sheet1
            st.success("✅ Google Cloud Auth successful! Bot is ready.")
        except Exception as e:
            st.error(f"❌ Google Auth Failed: {e}")
            st.stop()

    with st.spinner("2. Pinging Virginia Master REST API..."):
        try:
            response = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": "20261"}, timeout=15)
            if response.status_code != 200:
                st.error(f"❌ LIS API Failed. Status: {response.status_code}")
                st.stop()
            
            data = response.json()
            
            # --- THE REAL FIX ---
            # The data is already a flat list. No unpacking loop needed.
            all_bills = data.get("Legislations", [])
            
            st.success(f"✅ LIS Payload received! Found {len(all_bills)} bills.")
        except Exception as e:
            st.error(f"❌ LIS API Crash: {e}")
            st.stop()

    with st.spinner("3. Blasting data into Google Sheets..."):
        try:
            sheet_data = [["Bill Number", "Title", "Current Status"]] 
            
            for item in all_bills[:50]:
                bill_number = item.get("LegislationNumber", "Unknown")
                title = item.get("Description", "No Title")
                status = item.get("CurrentStatus", "Unknown")
                sheet_data.append([bill_number, title, status])
            
            worksheet.clear()
            worksheet.update(values=sheet_data, range_name="A1")
            
            st.balloons()
            st.success("🎉 DATABASE BRIDGE COMPLETE! Go look at your Google Sheet!")
            
        except Exception as e:
            st.error(f"❌ Write to Google Sheets Failed: {e}")
