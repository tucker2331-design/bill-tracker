import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v604 Pre-Flight Check", page_icon="✈️", layout="wide")
st.title("✈️ v604: The 'Pre-Flight' Check (Headers)")

session = requests.Session()
# MIMIC THE BROWSER EXACTLY
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'WebAPIKey': API_KEY,
    'Referer': 'https://lis.virginia.gov/committee/committee-legislation/H01', # Claim we are on the page
    'Origin': 'https://lis.virginia.gov',
    'X-Requested-With': 'XMLHttpRequest'
}

def run_header_fix():
    st.subheader("Step 1: Testing with Browser Headers...")
    
    # We go back to the endpoint that "worked" (gave 200 OK) but failed content
    url = f"{API_BASE}/CommitteeLegislation/api/GetCommitteeLegislationListAsync"
    
    # We try GET first (Standard for lists)
    params = {
        "sessionCode": SESSION_CODE,
        "committeeId": 1 # Agriculture (Confirmed ID)
    }
    
    st.write(f"🚀 GET Request to: `{url}`")
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            # CHECK CONTENT TYPE BEFORE PARSING
            c_type = resp.headers.get("Content-Type", "")
            st.caption(f"📡 Response Type: `{c_type}`")
            
            if "json" in c_type:
                data = resp.json()
                st.success("🎉 **VICTORY!** JSON Received!")
                
                # Unwrap logic
                bills = []
                if isinstance(data, dict):
                     st.write(f"Keys: {list(data.keys())}")
                     if "Legislation" in data: bills = data["Legislation"]
                     elif "Items" in data: bills = data["Items"]
                elif isinstance(data, list):
                    bills = data
                    
                if bills:
                    st.dataframe(bills[:5])
                else:
                    st.warning("⚠️ Empty List (but valid JSON!)")
            else:
                st.error("❌ Still receiving HTML (The website detected us).")
                st.text("Preview:")
                st.code(resp.text[:200])
        else:
            st.error(f"❌ Status {resp.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Header Fix"):
    run_header_fix()
