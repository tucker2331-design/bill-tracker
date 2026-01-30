import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525 # Known ID for HB1

st.set_page_config(page_title="v1100 Full Detail Probe", page_icon="🔬", layout="wide")
st.title("🔬 v1100: The 'Full Detail' Probe")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_detail_probe():
    st.subheader(f"Step 1: Fetching Master Object for HB1 (ID: {HB1_ID})...")
    
    # We try the "Main Object" endpoint from your Heist list
    # This is different from "Version" or "History"
    url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDAsync"
    
    # Try GET first (Standard for ID fetch)
    params = {"legislationId": HB1_ID, "sessionCode": SESSION_CODE}
    
    try:
        r = session.get(url, headers=headers, params=params, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if data:
                st.success("✅ Master Object Retrieved!")
                
                # EXTRACT CRITICAL INFO
                c_id = data.get("CommitteeId")
                c_name = data.get("CommitteeName")
                status = data.get("Status")
                
                st.info(f"📍 **Committee Info:** ID `{c_id}` | Name: `{c_name}`")
                st.info(f"🔄 **Current Status:** `{status}`")
                
                with st.expander("View Full JSON Payload"):
                    st.json(data)
            else:
                st.warning("⚠️ 200 OK (Empty Result)")
        
        elif r.status_code == 405:
            st.error("❌ 405 Method Not Allowed. Switching to POST...")
            # Retry with POST
            r2 = session.post(url, headers=headers, json=params, timeout=5)
            if r2.status_code == 200:
                data = r2.json()
                st.success("✅ POST Worked!")
                st.json(data)
            else:
                st.error(f"❌ POST Failed: {r2.status_code}")
                
        else:
            st.error(f"❌ Status {r.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Detail Probe"):
    run_detail_probe()
