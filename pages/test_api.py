import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# WE TEST TWO "KNOWN GOOD" ERAS
TESTS = [
    {"label": "2025 Regular Session", "code": "20251", "comm_id": 1},
    {"label": "2024 Regular Session", "code": "20241", "comm_id": 1}
]

st.set_page_config(page_title="v1900 Time Machine Proof", page_icon="⏳", layout="wide")
st.title("⏳ v1900: The 'Time Machine' Proof")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_time_machine():
    url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
    
    for t in TESTS:
        st.subheader(f"Testing {t['label']} (Code: {t['code']})...")
        
        # We use the payload that works for Advanced Search (POST)
        payload = {
            "SessionCode": t['code'],
            "CommitteeId": t['comm_id'],
            "ChamberCode": "H"
        }
        
        try:
            r = session.post(url, headers=headers, json=payload, timeout=8)
            
            if r.status_code == 200:
                data = r.json()
                
                # Unwrap
                bills = []
                if isinstance(data, dict):
                     if "Legislation" in data: bills = data["Legislation"]
                     elif "Items" in data: bills = data["Items"]
                     elif "Results" in data: bills = data["Results"]
                elif isinstance(data, list):
                    bills = data
                
                if bills:
                    st.success(f"🎉 **PROOF!** Found {len(bills)} bills in {t['label']}!")
                    st.dataframe(bills[:5]) # Show first 5
                    
                    # Verify they are actually in committee
                    sample = bills[0]
                    st.caption(f"Sample Bill: {sample.get('LegislationNumber')} | Status: {sample.get('Status')}")
                else:
                    st.warning(f"⚠️ {t['label']}: 200 OK (Empty List).")
                    
            elif r.status_code == 404:
                st.error(f"❌ {t['label']}: 404 Not Found")
            else:
                st.error(f"❌ {t['label']}: Failed {r.status_code}")
                
        except Exception as e:
            st.error(f"Error: {e}")
        
        st.divider()

    st.info("💡 **CONCLUSION:** If these lists populate, your code works. 2026 is just empty because bills haven't been referred yet.")

if st.button("🔴 Run Time Machine"):
    run_time_machine()
