import streamlit as st
import requests
import pandas as pd
import json
import time

# --- CONFIGURATION ---
# 🔑 REPLACE THIS with your actual API Key
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v2 Shadow Tracker", page_icon="🧪", layout="wide")
st.title("🧪 v2 Shadow Tracker (API Version)")

# --- API HANDLER ---
def fetch_api_calendar(chamber_code):
    url = "https://lis.virginia.gov/Calendar/api/getcalendarlistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": chamber_code}
    
    try:
        start_time = time.time()
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        duration = round(time.time() - start_time, 2)
        
        if resp.status_code == 200:
            return resp.json(), duration, None
        elif resp.status_code == 401:
            return {}, 0, "❌ Auth Failed (Check Key)"
        else:
            return {}, 0, f"❌ Error {resp.status_code}"
            
    except Exception as e:
        return {}, 0, f"💥 Connection Error: {e}"

# --- MAIN LOGIC ---
h_data, h_time, h_err = fetch_api_calendar("H")
s_data, s_time, s_err = fetch_api_calendar("S")

# --- SIDEBAR (CONTROLS & DEBUG) ---
with st.sidebar:
    st.header("⚙️ Monitor Controls")
    auto_refresh = st.toggle("🔄 Auto-Refresh (Live Monitor)", value=False)
    refresh_rate = st.slider("Refresh Rate (Seconds)", 10, 300, 60)
    
    if st.button("🚀 Force Refresh Now", type="primary"):
        st.rerun()

    st.divider()
    st.header("👨‍💻 Developer Data")
    
    # DEBUG BOX: HOUSE
    with st.expander("🔍 House Raw Data", expanded=False):
        if h_data: st.json(h_data)
        else: st.warning("No House Data")
        
    # DEBUG BOX: SENATE
    with st.expander("🔍 Senate Raw Data", expanded=False):
        if s_data: st.json(s_data)
        else: st.warning("No Senate Data")

# --- UI DISPLAY ---
col1, col2 = st.columns(2)

# HOUSE COLUMN
with col1:
    st.subheader("🏛️ House Calendar Files")
    if h_err:
        st.error(h_err)
    else:
        # SAFE PARSING: Look specifically for the "Calendars" key
        calendars = h_data.get("Calendars", [])
        st.success(f"🟢 Online ({h_time}s) - Found {len(calendars)} Calendar Days")
        
        if len(calendars) == 0:
            st.info("API returned no calendar entries.")
        
        for item in calendars:
            # Each 'item' is a day on the calendar
            date_str = item.get("CalendarDate", "Unknown Date").split("T")[0]
            desc = item.get("Description", "Calendar")
            
            with st.expander(f"📅 {date_str} - {desc}"):
                # Loop through the FILES attached to this day
                files = item.get("CalendarFiles", [])
                if files:
                    for f in files:
                        f_url = f.get("FileURL", "#")
                        st.markdown(f"📄 [Download File]({f_url}) (ID: {f.get('CalendarFileID')})")
                else:
                    st.caption("No files attached.")

# SENATE COLUMN
with col2:
    st.subheader("🏛️ Senate Calendar Files")
    if s_err:
        st.error(s_err)
    else:
        calendars = s_data.get("Calendars", [])
        st.success(f"🟢 Online ({s_time}s) - Found {len(calendars)} Calendar Days")
        
        if len(calendars) == 0:
            st.info("API returned no calendar entries.")
            
        for item in calendars:
            date_str = item.get("CalendarDate", "Unknown Date").split("T")[0]
            desc = item.get("Description", "Calendar")
            
            with st.expander(f"📅 {date_str} - {desc}"):
                files = item.get("CalendarFiles", [])
                if files:
                    for f in files:
                        f_url = f.get("FileURL", "#")
                        st.markdown(f"📄 [Download File]({f_url}) (ID: {f.get('CalendarFileID')})")
                else:
                    st.caption("No files attached.")

# --- AUTO REFRESH LOOP ---
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
