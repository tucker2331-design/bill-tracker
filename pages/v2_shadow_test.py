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

# ⚠️ Architect: Paste your exact Google Sheet ID here:
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"

st.markdown("This script pulls the universal JSON data and uses the `tracker-bot` Service Account to write it directly into your private Google Sheet.")

if st.button("🔥 Execute Database Bridge (Write to Sheets)"):
    if SPREADSHEET_ID == "INSERT_YOUR_SPREADSHEET_ID_HERE":
        st.error("🛑 Hold up! You need to paste your Spreadsheet ID into Line 16 of the code first.")
        st.stop()

    with st.spinner("1. Authenticating with Google Cloud Vault..."):
        try:
            # Wake up the bot using the secrets you pasted into Streamlit Cloud
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
            # Open the specific spreadsheet
            sh = gc.open_by_key(SPREADSHEET_ID)
            worksheet = sh.sheet1
            st.success("✅ Google Cloud Auth successful! Bot is ready.")
        except Exception as e:
            st.error(f"❌ Google Auth Failed. Did you share the sheet with the bot's email? Error: {e}")
            st.stop()

    with st.spinner("2. Pinging Virginia Master REST API..."):
        try:
            response = requests.get(TARGET_URL, headers=HEADERS, params={"sessionCode": "20261"}, timeout=15)
            if response.status_code != 200:
                st.error(f"❌ LIS API Failed. Status: {response.status_code}")
                st.stop()
            
            data = response.json()
            items = data.get("ListItems", data) if isinstance(data, dict) else data
            st.success(f"✅ LIS Payload received! Found {len(items)} bills.")
        except Exception as e:
            st.error(f"❌ LIS API Crash: {e}")
            st.stop()

    with st.spinner("3. Blasting data into Google Sheets..."):
        try:
            # We will format the first 50 bills just to test the bridge without hitting any timeout limits
            sheet_data = [["Bill Number", "Title", "Current Status"]] # These are the column headers
            
            for item in items[:50]:
                bill_number = item.get("LegislationNumber", "Unknown")
                title = item.get("Description", "No Title")
                status = item.get("CurrentStatus", "Unknown")
                sheet_data.append([bill_number, title, status])
            
            # Wipe the sheet clean, then write the new data block instantly
            worksheet.clear()
            worksheet.update(values=sheet_data, range_name="A1")
            
            st.balloons()
            st.success("🎉 DATABASE BRIDGE COMPLETE! Go look at your Google Sheet!")
            
        except Exception as e:
            st.error(f"❌ Write to Google Sheets Failed: {e}")
