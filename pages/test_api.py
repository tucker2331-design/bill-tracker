import streamlit as st
import requests
from datetime import datetime

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
# The Key we confirmed works (gave us 204, not 401)
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v503 Future Logic", page_icon="🔮", layout="wide")
st.title("🔮 v503: The Future-Only Logic Probe")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def probe_future_logic():
    st.subheader("Step 1: Finding a Valid 2026 Meeting...")
    
    # We use the Schedule API because we know it works (Status 200)
    url = f"{API_BASE}/Schedule/api/getschedulelistasync"
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} 
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            st.error(f"❌ Schedule API Failed: {resp.status_code}")
            return

        data = resp.json()
        events = data.get("Schedules", [])
        
        # --- THE LOGIC FILTER ---
        # We strictly filter for FUTURE dates to ensure the IDs are active/valid.
        today_str = datetime.now().strftime("%Y-%m-%d")
        future_events = []
        
        for e in events:
            s_date = e.get("ScheduleDate", "")
            # Must be in the future AND not cancelled
            if s_date >= today_str and not e.get("IsCancelled"):
                future_events.append(e)
        
        if not future_events:
            st.warning("⚠️ No future meetings found in House schedule. (Are we out of session?)")
            return

        # Sort to get the VERY NEXT meeting
        future_events.sort(key=lambda x: x.get("ScheduleDate"))
        target = future_events[0]
        
        st.success(f"✅ Locked on Active Target: **{target.get('OwnerName')}**")
        st.info(f"📅 Date: {target.get('ScheduleDate')} (2026 confirmed)")
        
        # --- STEP 2: VERIFY THE KEYS ---
        st.divider()
        st.subheader("🔎 IDs for this Meeting")
        
        ids = {
            "ScheduleId": target.get("ScheduleId"),
            "CommitteeId": target.get("CommitteeId"),
            "MeetingId": target.get("MeetingId")
        }
        st.json(ids)
        
        if not ids['ScheduleId']:
            st.error("🛑 CRITICAL: ScheduleId is still NULL. The API might not be providing IDs for this meeting type.")
            return

        # --- STEP 3: THE BRIDGE TEST ---
        st.divider()
        st.subheader("🧪 Testing the Bridge (Calendar Service)")
        st.write("Targeting `Calendar/api/GetDocketListAsync` with the valid ID...")
        
        # We fire the probe using the ScheduleID we just found
        docket_url = f"{API_BASE}/Calendar/api/GetDocketListAsync"
        docket_params = {"sessionCode": SESSION_CODE, "scheduleId": ids['ScheduleId']}
        
        r = session.get(docket_url, headers=headers, params=docket_params, timeout=5)
        
        if r.status_code == 200:
            d_data = r.json()
            if d_data:
                st.success(f"🎉 **PROOF OF LOGIC ACHIEVED!** Found {len(d_data)} items on the docket.")
                st.json(d_data)
                st.balloons()
            else:
                st.warning("⚠️ Status 200 (OK), but the list is empty. (Maybe no bills assigned yet?)")
        elif r.status_code == 204:
            st.info("⚪ Status 204: Valid ID, but server says 'No Content' (Empty Docket).")
        else:
            st.error(f"❌ Status {r.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Future Probe"):
    probe_future_logic()
