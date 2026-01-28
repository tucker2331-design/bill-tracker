import streamlit as st
import requests

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
COMMITTEE_ID = "18" # Internal ID for Privileges & Elections
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v400 The Paydirt", page_icon="🏆", layout="wide")
st.title("🏆 v400: The Paydirt")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Webapikey': WEB_API_KEY
}

def probe(service, action, params):
    url = f"{BASE_URL}/{service}/api/{action}"
    st.write(f"🚀 Launching probe at: `{service}/{action}`")
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                st.success("✅ **CONFIRMED HIT!** Payload Received:")
                st.json(data)
                return True
            else:
                st.warning("⚠️ Status 200, but data is empty.")
        elif resp.status_code == 404:
            st.error("❌ 404 Not Found")
        else:
            st.error(f"❌ Status {resp.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")
    return False

if st.button("🔴 Probe Golden Targets"):
    
    st.subheader("Target 1: The Calendar Service")
    # This is the most likely winner based on the name
    probe("Calendar", "GetDocketListAsync", {
        "sessionCode": SESSION_CODE, 
        "committeeId": COMMITTEE_ID
    })

    st.divider()

    st.subheader("Target 2: The LegislationEvent Service")
    # Meetings are 'Events', so bills might be listed here
    probe("LegislationEvent", "GetLegislationEventListAsync", {
        "sessionCode": SESSION_CODE, 
        "committeeId": COMMITTEE_ID
    })
