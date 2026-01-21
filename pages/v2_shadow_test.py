import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime
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
        # We record the start time to measure speed
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
st.caption("This app connects DIRECTLY to the LIS Database. No CSVs. No Lag.")

# Sidebar Controls
with st.sidebar:
    st.header("⚙️ Controls")
    auto_refresh = st.toggle("🔄 Auto-Refresh (Live Monitor)", value=False)
    refresh_rate = st.slider("Refresh Rate (Seconds)", 10, 300, 60)
    
    if st.button("🚀 Force Refresh Now", type="primary"):
        st.rerun()
    
    st.divider()
    st.markdown("**Debug Tools**")
    bill_search = st.text_input("🔍 Search Raw Data for Bill (e.g. HB1)", "")

# --- MAIN LOGIC ---

# 1. Fetch Data
col1, col2 = st.columns(2)

with col1:
    st.subheader("🏛️ House Calendar")
    h_data, h_time, h_err = fetch_api_calendar("H")
    
    if h_err:
        st.error(h_err)
    else:
        st.success(f"🟢 Online ({h_time}s) - {len(h_data)} Meetings Found")
        
        # Display House Meetings
        if h_data:
            for meeting in h_data:
                # API usually returns keys like 'Description', 'MeetingDate', 'VoteTime'
                # We try to handle different key variations safely
                desc = meeting.get('CommitteeName') or meeting.get('description') or "Unknown Committee"
                m_date = meeting.get('MeetingDate') or meeting.get('meetingDate')
                m_time = meeting.get('MeetingTime') or meeting.get('meetingTime') or "TBA"
                
                with st.expander(f"📅 {desc} - {m_time}"):
                    st.write(f"**Date:** {m_date}")
                    st.json(meeting) # Show full raw details for debugging

with col2:
    st.subheader("🏛️ Senate Calendar")
    s_data, s_time, s_err = fetch_api_calendar("S")
    
    if s_err:
        st.error(s_err)
    else:
        st.success(f"🟢 Online ({s_time}s) - {len(s_data)} Meetings Found")
        
        # Display Senate Meetings
        if s_data:
            for meeting in s_data:
                desc = meeting.get('CommitteeName') or meeting.get('description') or "Unknown Committee"
                m_date = meeting.get('MeetingDate') or meeting.get('meetingDate')
                m_time = meeting.get('MeetingTime') or meeting.get('meetingTime') or "TBA"
                
                with st.expander(f"📅 {desc} - {m_time}"):
                    st.write(f"**Date:** {m_date}")
                    st.json(meeting)

# --- DEBUG SEARCH ---
if bill_search:
    st.divider()
    st.header(f"🕵️ Deep Search: '{bill_search}'")
    found_any = False
    
    # Search House Data
    for m in h_data:
        if bill_search.upper() in str(m).upper():
            st.warning(f"Found in House: {m.get('CommitteeName', 'Unknown')}")
            st.json(m)
            found_any = True
            
    # Search Senate Data
    for m in s_data:
        if bill_search.upper() in str(m).upper():
            st.warning(f"Found in Senate: {m.get('CommitteeName', 'Unknown')}")
            st.json(m)
            found_any = True
            
    if not found_any:
        st.info(f"❌ '{bill_search}' not found in any ACTIVE API calendar entries.")

# --- AUTO REFRESH LOOP ---
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
