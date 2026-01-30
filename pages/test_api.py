import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" # 2026 Regular
COMMITTEE_ID = 1      # Agriculture

st.set_page_config(page_title="v2100 GET Bypass", page_icon="↩️", layout="wide")
st.title("↩️ v2100: The 'GET' Bypass")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_get_bypass():
    # We are retrying the "Advanced Search" endpoint, but with GET
    url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
    
    st.subheader(f"Targeting: `{url}` (Method: GET)")
    
    # CONVERT PAYLOAD TO QUERY PARAMS
    # Note: trying both PascalCase and camelCase keys just to be safe
    params = {
        "sessionCode": SESSION_CODE,
        "committeeId": COMMITTEE_ID,
        "chamberCode": "H"
    }
    
    st.write("🚀 Sending GET Params:", params)
    
    try:
        r = session.get(url, headers=headers, params=params, timeout=10)
        
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
                st.success(f"🎉 **BYPASS SUCCESS!** Found {len(bills)} bills using GET!")
                st.dataframe(bills[:10])
                st.balloons()
            else:
                st.warning("⚠️ 200 OK (Empty List) - GET worked, but returned no data.")
                
        elif r.status_code == 405:
            st.error("❌ 405 Method Not Allowed (The server specifically forbids GET on this endpoint).")
        else:
            st.error(f"❌ Failed: {r.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

    # --- TEST 2: HISTORY BYPASS ---
    st.divider()
    st.subheader("Test 2: History GET Bypass (2024 Control Bill)")
    # We try to get history for the 2024 Control Bill (ID 91072) using GET
    hist_url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
    hist_params = {"legislationId": 91072, "sessionCode": "20241"}
    
    try:
        r2 = session.get(hist_url, headers=headers, params=hist_params, timeout=5)
        if r2.status_code == 200:
             st.success("🎉 **HISTORY UNLOCKED via GET!**")
             st.json(r2.json())
        else:
             st.error(f"❌ History GET Failed: {r2.status_code}")
    except:
        pass

if st.button("🔴 Run GET Bypass"):
    run_get_bypass()
