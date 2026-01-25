import streamlit as st
import requests
import concurrent.futures
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v85 Clean Calendar", page_icon="📆", layout="wide")
st.title("📆 v85: Official Session Calendar")

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_raw_schedule():
    # This is the endpoint that SUCCEEDED in v84
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

# --- MAIN LOGIC ---
all_events = get_raw_schedule()

# 1. FILTER: Only "Session" Events (The Big Floor Meetings)
# We look for "Convene" or "Session" or just "House"/"Senate" as the owner
sessions = [
    m for m in all_events 
    if "Convene" in m.get("OwnerName", "") 
    or "Session" in m.get("OwnerName", "") 
    or m.get("OwnerName") in ["House", "Senate"]
]

# 2. FILTER: Only Future Dates (No history)
today = datetime.now().date()
upcoming_sessions = []

for s in sessions:
    raw_date = s.get("ScheduleDate", "").split("T")[0]
    if raw_date:
        s_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        if s_date >= today:
            s['DateObj'] = s_date
            upcoming_sessions.append(s)

# Sort by date
upcoming_sessions.sort(key=lambda x: x['DateObj'])

# --- DISPLAY ---
if not upcoming_sessions:
    st.info("No upcoming sessions found.")
else:
    # Group by Date for a cleaner view
    dates = sorted(list(set(s['DateObj'] for s in upcoming_sessions)))
    
    # Show next 7 available dates
    cols = st.columns(min(len(dates), 7))
    
    for i, date_val in enumerate(dates[:7]):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            # Find events for this specific day
            day_events = [s for s in upcoming_sessions if s['DateObj'] == date_val]
            
            for event in day_events:
                name = event.get("OwnerName").replace("Virginia ", "").replace(" of Delegates", "")
                time_val = event.get("ScheduleTime")
                
                # CLEAN DISPLAY CARD
                with st.container(border=True):
                    st.markdown(f"**{name}**")
                    if time_val:
                        st.success(f"⏰ {time_val}")
                    else:
                        st.warning("Time TBA")
