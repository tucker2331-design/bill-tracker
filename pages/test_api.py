import streamlit as st
import requests
import concurrent.futures
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v84 Simple Tracker", page_icon="🏛️", layout="wide")
st.title("🏛️ v84: The Simple Tracker")
st.markdown("No scrapers. No filters. Just the raw data from the API.")

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_raw_schedule():
    # We use the method we KNOW works
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        session = requests.Session()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: raw_items.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw_items.extend(s.result().json().get("Schedules", []))
            
        return raw_items
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

# --- MAIN APP ---
meetings = get_raw_schedule()

# Filter for just House/Senate Sessions (The "Convening" events)
sessions = [
    m for m in meetings 
    if "Convene" in m.get("OwnerName", "") 
    or "Session" in m.get("OwnerName", "") 
    or m.get("OwnerName") in ["House", "Senate"]
]

if not sessions:
    st.warning("No 'Session' or 'Convene' events found in the API feed.")
else:
    # Sort by date
    sessions.sort(key=lambda x: x.get("ScheduleDate", ""))

    st.subheader(f"Found {len(sessions)} Floor Sessions")
    
    # Display them simply
    cols = st.columns(4)
    for i, s in enumerate(sessions):
        date_str = s.get("ScheduleDate", "").split("T")[0]
        name = s.get("OwnerName")
        raw_time = s.get("ScheduleTime") # THE RAW TIME
        
        # CARD DISPLAY
        with cols[i % 4]:
            with st.container(border=True):
                st.caption(date_str)
                st.markdown(f"**{name}**")
                
                if raw_time:
                    st.success(f"⏰ {raw_time}")
                else:
                    st.error("Time is blank in API")
                
                with st.expander("Raw Data"):
                    st.json(s)
