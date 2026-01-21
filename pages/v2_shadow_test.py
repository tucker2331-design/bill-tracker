import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v3.1 Schedule Inspector", page_icon="🕵️", layout="wide")
st.title("🕵️ v3.1: Inspecting the Schedule")

def fetch_and_inspect_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} 
    
    with st.spinner("Downloading Master Schedule..."):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                schedules = data.get("Schedules", [])
                st.success(f"✅ Loaded {len(schedules)} Schedule Entries")
                
                # --- INTELLIGENT FILTER ---
                # We only want to look at RECENT or UPCOMING meetings to see valid data
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                found_count = 0
                for item in schedules:
                    # Try to find a date key (API keys can vary, checking common ones)
                    raw_date = item.get("ScheduleDate") or item.get("MeetingDate") or ""
                    
                    # If we find a meeting for TODAY or TOMORROW, show its full details
                    if raw_date and raw_date.startswith(today_str):
                        st.divider()
                        st.subheader(f"📅 Found Meeting for {raw_date}")
                        st.write(f"**Description:** {item.get('Description')}")
                        
                        with st.expander("🔥 CLICK HERE - DATA ANATOMY", expanded=True):
                            st.json(item) # <--- THIS IS THE KEY PART
                        
                        found_count += 1
                        if found_count >= 3: break # Just show us top 3 to avoid clutter
                
                if found_count == 0:
                    st.warning("No meetings found specifically for today. Showing the very last item in the list instead:")
                    if schedules:
                        st.json(schedules[-1])

        except Exception as e:
            st.error(f"Error: {e}")

if st.button("🚀 Analyze Schedule Data"):
    fetch_and_inspect_schedule()
