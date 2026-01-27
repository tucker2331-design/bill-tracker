import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
# We are using the endpoint discovered in your screenshot
API_ENDPOINT = "https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync"
SESSION_CODE = "20261" 

st.set_page_config(page_title="v124 API Key", page_icon="🗝️", layout="wide")
st.title("🗝️ v124: The API Key (JSON Payload Switch)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Content-Type': 'application/json', # Critical change: Telling server we are sending JSON
    'Accept': 'application/json'
}

# --- THE HIDDEN API PROBE ---
def probe_hidden_api(committee_id):
    """
    Attempts to hit the internal API using a JSON POST/GET payload.
    """
    
    # Payload matches the parameters you saw in DevTools
    payload = {
        "sessionCode": SESSION_CODE,
        "committeeId": committee_id
    }
    
    st.markdown(f"### 📡 Attempting Breach on `{committee_id}`...")
    
    # METHOD 1: GET with JSON body (Rare but used by some legacy .NET apps)
    try:
        st.write("🔹 **Attempt 1:** GET Request with Query Params...")
        resp = session.get(API_ENDPOINT, headers=HEADERS, params=payload, timeout=5)
        if resp.status_code == 200:
            st.success("✅ Attempt 1 Success!")
            return show_results(resp.json())
        else:
            st.warning(f"Attempt 1 Failed ({resp.status_code}). Trying Post...")
    except Exception as e:
        st.error(f"Error: {e}")

    # METHOD 2: POST with JSON body (Standard for 'Async' endpoints)
    try:
        st.write("🔹 **Attempt 2:** POST Request with JSON Body...")
        # Note: We switch to POST because 'Bad Request' often means 'Wrong Verb' or 'Missing Body'
        resp = session.post(API_ENDPOINT, headers=HEADERS, json=payload, timeout=5)
        
        if resp.status_code == 200:
            st.success("✅ Attempt 2 Success!")
            return show_results(resp.json())
        else:
            st.error(f"❌ Attempt 2 Failed: {resp.status_code}")
            st.text(resp.text[:500])
            
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")

def show_results(data):
    if not data: return
    
    # Inspect for Subcommittees
    if "SubCommittees" in data:
        subs = data["SubCommittees"]
        st.success(f"🎉 FOUND {len(subs)} SUBCOMMITTEES!")
        
        # Formatting for readability
        clean_list = []
        for sub in subs:
            clean_list.append({
                "Name": sub.get("Name"),
                "GHOST ID (Secret)": sub.get("CommitteeId"), 
                "ParentId": sub.get("ParentCommitteeId")
            })
        st.table(clean_list)
    else:
        st.warning("JSON received, but 'SubCommittees' key is missing.")
        st.json(data)

# --- UI ---
st.sidebar.header("🗝️ API Key Tool")
target_id = st.sidebar.text_input("Target Committee ID:", value="H18") # H18 is Privileges

if st.sidebar.button("🔴 Test Hidden API"):
    probe_hidden_api(target_id)
