import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
BASE_URL = "https://lis.virginia.gov"

st.set_page_config(page_title="API Method Hunter", layout="wide")
st.title("🕵️‍♂️ API Method Hunter")
st.markdown("This tool ignores the 'Schedule' and hunts for the **Session Time** in the other services.")

# List of likely candidates based on LIS naming conventions
candidates = [
    # TARGET 1: The "Session" Service (Most Likely for times)
    {"service": "Session", "method": "getsessionlist", "desc": "List of all session days"},
    {"service": "Session", "method": "getsessioninfo", "desc": "Metadata about the session"},
    {"service": "Session", "method": "getdays", "desc": "List of legislative days"},
    
    # TARGET 2: The "Calendar" Service (Secondary target)
    {"service": "Calendar", "method": "getcalendarlist", "desc": "List of daily calendars"},
    {"service": "Calendar", "method": "getdailycalendar", "desc": "The specific agenda for today"},
]

if st.button("🚀 Start Hunt"):
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    found_something = False
    
    for c in candidates:
        url = f"{BASE_URL}/{c['service']}/api/{c['method']}"
        
        # We try both chambers
        for chamber in ["H", "S"]:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # We only care if it's a LIST or has DATA
                    # Check if it's just an empty error message
                    is_valid = False
                    if isinstance(data, list) and len(data) > 0: is_valid = True
                    if isinstance(data, dict) and len(data.keys()) > 0: is_valid = True
                    
                    if is_valid:
                        found_something = True
                        st.success(f"✅ HIT! [{c['service']}] {c['method']} ({chamber})")
                        
                        # SEARCH FOR TIME
                        # Convert to string to search for "Time" or "Convene"
                        dump = json.dumps(data).lower()
                        if "time" in dump or "convene" in dump or "start" in dump:
                            st.balloons()
                            st.markdown(f"### 🎯 JACKPOT: Found 'Time' data in `{c['method']}`")
                            st.json(data) # Show the user the gold
                            st.stop() # Stop looking, we found it
                        else:
                            with st.expander(f"Data found in {c['method']}, but no obvious time..."):
                                st.json(data)
                                
            except Exception as e:
                pass # method didn't work, keep moving

    if not found_something:
        st.error("❌ No luck. The method names might be non-standard.")
        st.info("Please click the 'Session' and 'Calendar' links in your documentation screenshot and tell me the method names listed there.")
