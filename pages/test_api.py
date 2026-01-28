import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" # The Key you provided

st.set_page_config(page_title="v502 Logic Probe", page_icon="🧬", layout="wide")
st.title("🧬 v502: The Logic Probe (Calendar → Bill Bridge)")

# --- NETWORK SETUP ---
session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY # Using the confirmed key
}

def probe_bridge():
    st.subheader("Step 1: Fetching the 'Master Schedule'...")
    
    # 1. Get the Schedule
    url = f"{API_BASE}/Schedule/api/getschedulelistasync"
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} # Start with House
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        if resp.status_code != 200:
            st.error(f"❌ Schedule API Failed: {resp.status_code}")
            return

        data = resp.json()
        events = data.get("Schedules", [])
        
        # Filter for a "Real" meeting (Not cancelled, has a Committee)
        upcoming = [e for e in events if not e.get("IsCancelled") and "Committee" in e.get("OwnerName", "")]
        
        if not upcoming:
            st.warning("⚠️ No active committee meetings found in schedule.")
            return

        # PICK THE FIRST TARGET
        target = upcoming[0]
        st.success(f"✅ Locked on Target: **{target.get('OwnerName')}** ({target.get('ScheduleDate')})")
        
        # --- STEP 2: DUMP THE IDS (THE DEVELOPER WINDOW) ---
        st.divider()
        st.subheader("🔎 Extracted IDs (The Keys)")
        
        ids = {
            "ScheduleId": target.get("ScheduleId"),
            "CommitteeId": target.get("CommitteeId"), # Usually internal integer
            "MeetingId": target.get("MeetingId"), # Might be null
            "OwnerId": target.get("OwnerId"),
            "EventId": target.get("EventId"), # The "Event" theory
            "Link": target.get("LinkUrl") # Sometimes the link IS the data
        }
        st.json(ids)
        
        # --- STEP 3: FIRE THE PROBES ---
        st.divider()
        st.subheader("🧪 API Probe Results")
        st.write("Attempting to fetch bills using these IDs...")

        # Probe A: Calendar Docket (The obvious one)
        # Try with ScheduleId and CommitteeId
        if ids['CommitteeId']:
            try_endpoint("Calendar/api/GetDocketListAsync", {"sessionCode": SESSION_CODE, "committeeId": ids['CommitteeId']}, "Docket by CommID")
        
        if ids['ScheduleId']:
            try_endpoint("Calendar/api/GetDocketListAsync", {"sessionCode": SESSION_CODE, "scheduleId": ids['ScheduleId']}, "Docket by ScheduleID")

        # Probe B: Legislation Event (The strong candidate)
        # If meetings are "LegislationEvents", maybe we can list them?
        if ids['CommitteeId']:
            try_endpoint("LegislationEvent/api/GetLegislationEventListAsync", {"sessionCode": SESSION_CODE, "committeeId": ids['CommitteeId']}, "Events by CommID")

        # Probe C: Committee Legislation (The Direct Inventory)
        if ids['CommitteeId']:
             try_endpoint("CommitteeLegislation/api/GetCommitteeLegislationListAsync", {"sessionCode": SESSION_CODE, "committeeId": ids['CommitteeId']}, "Legislation by CommID")

    except Exception as e:
        st.error(f"Critical Error: {e}")

def try_endpoint(path, params, label):
    url = f"{API_BASE}/{path}"
    st.markdown(f"**🔫 Firing: {label}** (`{path}`)")
    try:
        r = session.get(url, headers=headers, params=params, timeout=3)
        if r.status_code == 200:
            data = r.json()
            if data:
                st.success(f"🎉 **SUCCESS!** ({len(data)} items found)")
                with st.expander("View Data Payload"):
                    st.json(data)
            else:
                st.warning(f"⚠️ 200 OK (Empty List)")
        elif r.status_code == 204:
            st.info("⚪ 204 No Content")
        else:
            st.error(f"❌ Status {r.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Logic Probe"):
    probe_bridge()
