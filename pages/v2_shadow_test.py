import streamlit as st
import requests
import pandas as pd
import json
import time

# --- CONFIGURATION ---
# 🔑 REPLACE THIS with your actual API Key
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

# Setup the page
st.set_page_config(
    page_title="v2 Shadow Tracker (API Test)", 
    page_icon="🧪", 
    layout="wide"
)

# --- API HANDLER ---
def fetch_api_calendar(chamber_code):
    """
    Connects to the Official Virginia LIS API.
    chamber_code: 'H' or 'S'
    """
    url = "https://lis.virginia.gov/Calendar/api/getcalendarlistasync"
    
    headers = {
        "WebAPIKey": API_KEY,
        "Accept": "application/json"
    }
    
    params = {
        "sessionCode": SESSION_CODE,
        "chamberCode": chamber_code,
    }
    
    try:
        start_time = time.time()
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        duration = round(time.time() - start_time, 2)
        
        if resp.status_code == 200:
            return resp.json(), duration, None
        elif resp.status_code == 401:
            return [], 0, "❌ Auth Failed (Check Key)"
        else:
            return [], 0, f"❌ Error {resp.status_code}"
            
    except Exception as e:
        return [], 0, f"💥 Connection Error: {e}"

# --- UI LAYOUT ---
st.title("🧪 v2 Shadow Tracker (API Version)")

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Monitor Controls")
    st.caption("These controls let you keep this tab open as a live dashboard.")
    auto_refresh = st.toggle("🔄 Auto-Refresh (Live Monitor)", value=False)
    refresh_rate = st.slider("Refresh Rate (Seconds)", 10, 300, 60)
    
    if st.button("🚀 Force Refresh Now", type="primary"):
        st.rerun()
    
    st.divider()
    st.markdown("**Debug Tools**")
    bill_search = st.text_input("🔍 Search Raw Data for Bill (e.g. HB1)", "")

# --- MAIN LOGIC ---

col1, col2 = st.columns(2)

# HOUSE COLUMN
with col1:
    st.subheader("🏛️ House Calendar")
    h_data, h_time, h_err = fetch_api_calendar("H")
    
    if h_err:
        st.error(h_err)
    else:
        st.success(f"🟢 Online ({h_time}s) - {len(h_data)} Items Found")
        
        # --- DEVELOPER DATA DUMP (Screenshot this!) ---
        with st.expander("👨‍💻 RAW DATA (Open for Screenshot)", expanded=True):
            st.write("The API returned this data structure:")
            st.write(h_data)

        # CRASH-PROOF LOOP
        if h_data:
            for item in h_data:
                # If it's a simple string (which caused the error before)
                if isinstance(item, str):
                    st.info(f"📝 String Entry: {item}")
                
                # If it's a Dictionary (Object)
                elif isinstance(item, dict):
                    desc = item.get('CommitteeName') or item.get('description') or "Unknown"
                    m_time = item.get('MeetingTime') or "TBA"
                    st.write(f"**{desc}** at {m_time}")
                
                # If it's something else
                else:
                    st.warning(f"Unknown Format: {type(item)}")

# SENATE COLUMN
with col2:
    st.subheader("🏛️ Senate Calendar")
    s_data, s_time, s_err = fetch_api_calendar("S")
    
    if s_err:
        st.error(s_err)
    else:
        st.success(f"🟢 Online ({s_time}s) - {len(s_data)} Items Found")
        
        with st.expander("👨‍💻 RAW DATA (Open for Screenshot)"):
            st.write(s_data)
            
        if s_data:
            for item in s_data:
                if isinstance(item, str):
                    st.info(f"📝 String Entry: {item}")
                elif isinstance(item, dict):
                    desc = item.get('CommitteeName') or item.get('description') or "Unknown"
                    st.write(f"**{desc}**")

# --- AUTO REFRESH LOOP ---
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
