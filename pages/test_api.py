import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
API_URL = "https://lis.virginia.gov/Committee/api/getCommitteesAsync"
SESSION_CODE = "20261" 
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v134 JSON X-Ray", page_icon="🩻", layout="wide")
st.title("🩻 v134: The JSON X-Ray")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://lis.virginia.gov/',
    'Webapikey': WEB_API_KEY
}

def xray_response():
    st.write(f"🔐 **Authenticating...**")
    
    params = {"sessionCode": SESSION_CODE}
    
    try:
        resp = session.get(API_URL, headers=HEADERS, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            st.success("✅ **ACCESS GRANTED!** Payload Received.")
            
            # --- DEBUGGING THE STRUCTURE ---
            st.divider()
            st.subheader("🔍 X-Ray Results (Raw Data structure)")
            
            if isinstance(data, list):
                st.info(f"Type: LIST (Length: {len(data)})")
                if len(data) > 0:
                    st.write("**First Item Type:**", type(data[0]))
                    st.write("**First Item Preview:**", data[0])
            elif isinstance(data, dict):
                st.info(f"Type: DICTIONARY (Keys: {list(data.keys())})")
                st.json(data) # SHOW THE FULL JSON TO THE USER
            else:
                st.error(f"Unknown Type: {type(data)}")
                st.write(data)

        else:
            st.error(f"❌ Failed ({resp.status_code})")
            
    except Exception as e:
        st.error(f"Error: {e}")

# --- UI ---
st.sidebar.header("🩻 X-Ray Tool")
if st.sidebar.button("🔴 X-Ray API Response"):
    xray_response()
