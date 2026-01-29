import streamlit as st
import requests
from datetime import datetime

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v700 Master Key Fuzz", page_icon="🗝️", layout="wide")
st.title("🗝️ v700: The 'Master Key' Fuzz")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def run_fuzz():
    st.subheader("Step 1: Fetching Active Committees...")
    
    # 1. Get the list of committees so we have REAL IDs to test
    c_url = f"{API_BASE}/Committee/api/GetCommitteeListAsync"
    c_resp = session.get(c_url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
    
    if c_resp.status_code != 200:
        st.error("❌ Failed to get committee list.")
        return

    raw = c_resp.json()
    committees = []
    # Unwrap logic
    if isinstance(raw, dict) and "Committees" in raw: committees = raw["Committees"]
    elif isinstance(raw, list): committees = raw
    
    if not committees:
        st.error("❌ No committees found.")
        return
        
    st.success(f"✅ Loaded {len(committees)} Committees. Starting Fuzzing Sequence...")
    
    # 2. THE FUZZ LOOP
    docket_url = f"{API_BASE}/Calendar/api/GetDocketListAsync"
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # We test the first 5 committees to save time
    targets = committees[:5]
    
    for c in targets:
        c_id = c.get("CommitteeID")      # e.g., 1
        c_code = c.get("CommitteeNumber") # e.g., "H01"
        c_name = c.get("Name")
        
        with st.expander(f"🔫 Testing: {c_name} (ID: {c_id} | Code: {c_code})", expanded=True):
            
            # --- VARIATION A: Integer ID ---
            check_endpoint(docket_url, {"sessionCode": SESSION_CODE, "committeeId": c_id}, "Integer ID")
            
            # --- VARIATION B: String Code ---
            check_endpoint(docket_url, {"sessionCode": SESSION_CODE, "committeeId": c_code}, "String Code")
            
            # --- VARIATION C: Integer ID + Date ---
            check_endpoint(docket_url, {"sessionCode": SESSION_CODE, "committeeId": c_id, "date": today_str}, "Int ID + Date")

             # --- VARIATION D: String Code + Date ---
            check_endpoint(docket_url, {"sessionCode": SESSION_CODE, "committeeId": c_code, "date": today_str}, "String Code + Date")

def check_endpoint(url, params, label):
    try:
        r = session.get(url, headers=headers, params=params, timeout=2)
        if r.status_code == 200:
            data = r.json()
            if data:
                st.success(f"🎉 **JACKPOT! [{label}]** returned data!")
                st.json(data)
            else:
                st.warning(f"⚠️ [{label}] 200 OK (Empty)")
        elif r.status_code == 204:
            st.caption(f"⚪ [{label}] 204 No Content")
        else:
            st.caption(f"❌ [{label}] Status {r.status_code}")
    except:
        pass

if st.button("🔴 Run Master Key Fuzz"):
    run_fuzz()
