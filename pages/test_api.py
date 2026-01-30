import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525 # Confirmed correct

st.set_page_config(page_title="v1101 Plural Correction", page_icon="🧩", layout="wide")
st.title("🧩 v1101: The Plural Correction")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_plural_fix():
    st.subheader(f"Step 1: Fetching HB1 Master Record (ID: {HB1_ID})...")
    
    # CORRECT ENDPOINT (From Heist Screenshot 5.35.52 PM)
    # Note the 's' in IDs
    url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDsAsync"
    
    # Payload: The API likely expects a list of integers
    # We try two common formats for list payloads
    payload_A = {"legislationIds": [HB1_ID], "sessionCode": SESSION_CODE}
    payload_B = [HB1_ID] # Sometimes it just wants the raw list
    
    st.write(f"🚀 POSTing to `{url}`")
    
    try:
        # Attempt A (Named Parameter)
        r = session.post(url, headers=headers, json=payload_A, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            # Unwrap
            if isinstance(data, dict):
                 items = data.get("Legislation") or data.get("Items") or []
            elif isinstance(data, list):
                items = data
            else: items = []

            if items:
                target = items[0]
                st.success("🎉 **MASTER RECORD FOUND!**")
                
                # EXTRACT THE GOLD
                c_name = target.get("CommitteeName")
                c_id = target.get("CommitteeId")
                status = target.get("Status")
                
                st.info(f"📍 **Committee:** `{c_name}` (ID: {c_id})")
                st.info(f"🔄 **Status:** {status}")
                
                with st.expander("Full Data Payload"):
                    st.json(target)
            else:
                st.warning("⚠️ 200 OK but Empty List (Payload A)")
                
        else:
            st.error(f"❌ Attempt A Failed: {r.status_code}")
            
            # Backup: Try Attempt B (Raw List)
            st.write("Trying Payload B (Raw List)...")
            r2 = session.post(url, headers=headers, json=payload_B, timeout=5)
            if r2.status_code == 200:
                 st.success("✅ Payload B Worked!")
                 st.json(r2.json())
            else:
                 st.error(f"❌ Attempt B Failed: {r2.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Plural Fix"):
    run_plural_fix()
