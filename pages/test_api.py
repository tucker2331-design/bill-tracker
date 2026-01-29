import streamlit as st
import requests
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v506 Wide Net", page_icon="🕸️", layout="wide")
st.title("🕸️ v506: The 'Wide Net' Scanner")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def scan_wide_net():
    st.subheader("Scanning Next 7 Days (No Filters)...")
    
    url = f"{API_BASE}/Schedule/api/getschedulelistasync"
    found_events = []
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Check BOTH Chambers
        for chamber in ["H", "S"]:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = session.get(url, headers=headers, params=params, timeout=5)
            
            if resp.status_code == 200:
                events = resp.json().get("Schedules", [])
                for e in events:
                    # ONLY Filter: Must be in the future (or today)
                    if e.get("ScheduleDate", "") >= today_str:
                        e['Chamber'] = chamber
                        found_events.append(e)
    
        if not found_events:
            st.error("❌ No events found at all. (Check Session Code?)")
            return

        # Sort by Date
        found_events.sort(key=lambda x: (x.get("ScheduleDate"), x.get("ScheduleTime")))
        
        st.success(f"✅ Found {len(found_events)} Upcoming Events")
        st.write("Inspecting the first 5 events to find a valid ID...")
        
        # Display the first 10 events
        for i, e in enumerate(found_events[:10]):
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{e.get('OwnerName')}**")
                    st.caption(f"📅 {e.get('ScheduleDate')} | ⏰ {e.get('ScheduleTime')} | 🏛️ {e.get('Chamber')}")
                
                with c2:
                    # SHOW THE RAW IDS
                    s_id = e.get("ScheduleId")
                    c_id = e.get("CommitteeId")
                    
                    if s_id: 
                        st.success(f"🆔 S-ID: {s_id}")
                        # If we find a valid ID, let's test it immediately!
                        if st.button(f"🚀 Test S-ID {s_id}", key=f"btn_{i}"):
                            test_docket(s_id)
                    elif c_id:
                        st.info(f"🆔 C-ID: {c_id}")
                    else:
                        st.error("❌ NULL IDs")

    except Exception as e:
        st.error(f"Error: {e}")

def test_docket(s_id):
    st.write(f"Testing Docket for ScheduleID {s_id}...")
    url = f"{API_BASE}/Calendar/api/GetDocketListAsync"
    try:
        r = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "scheduleId": s_id}, timeout=3)
        if r.status_code == 200 and r.json():
            st.success("🎉 JACKPOT! Bills Found:")
            st.json(r.json())
        elif r.status_code == 204:
            st.warning("⚠️ 204 No Content (Empty Docket)")
        else:
            st.error(f"❌ Status {r.status_code}")
    except:
        st.error("Connection Error")

if st.button("🔴 Cast Wide Net"):
    scan_wide_net()
