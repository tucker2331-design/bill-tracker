import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v603 Protocol Shift", page_icon="📡", layout="wide")
st.title("📡 v603: The Protocol Shift (POST vs GET)")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json', # Critical for POST
    'WebAPIKey': API_KEY
}

def run_post_fix():
    st.subheader("Step 1: Fetching Committee 'Agriculture' (ID: 1)...")
    
    # We hardcode ID 1 because we proved it exists in v602
    target_id = 1
    target_name = "Agriculture, Chesapeake and Natural Resources"
    
    st.info(f"🎯 Target: **{target_name}** | Internal ID: `{target_id}`")
    
    st.divider()
    st.subheader("Step 2: Firing POST Request")
    
    # The endpoint that gave us 200 (but HTML) last time
    url = f"{API_BASE}/CommitteeLegislation/api/GetCommitteeLegislationListAsync"
    
    # PAYLOAD: Send as JSON body, not URL params
    payload = {
        "sessionCode": SESSION_CODE,
        "committeeId": target_id
    }
    
    st.write(f"🚀 POSTing to: `{url}`")
    st.caption(f"📦 Body: {payload}")
    
    try:
        # SWITCH TO POST
        resp = session.post(url, headers=headers, json=payload, timeout=5)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                
                # Check if it's the wrapper again
                real_bills = []
                if isinstance(data, dict):
                    if "Legislation" in data: real_bills = data["Legislation"]
                    elif "Items" in data: real_bills = data["Items"]
                    else:
                        st.warning("⚠️ Unknown Wrapper Format:")
                        st.json(data)
                elif isinstance(data, list):
                    real_bills = data
                
                if real_bills:
                    st.success(f"🎉 **VICTORY!** Found {len(real_bills)} bills!")
                    st.dataframe(real_bills[:10]) # Show first 10
                    st.balloons()
                else:
                    st.warning("⚠️ 200 OK (Empty List). Try another committee?")
                    
            except Exception as e:
                st.error(f"❌ JSON Decode Failed Again: {e}")
                st.text("Raw Response Preview (First 500 chars):")
                st.code(resp.text[:500])
                
        else:
            st.error(f"❌ Status {resp.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run POST Fix"):
    run_post_fix()
