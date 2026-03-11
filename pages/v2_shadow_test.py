import streamlit as st
import requests

st.set_page_config(page_title="Phase 1 Probe", layout="wide")
st.title("🚀 Phase 1: LIS Legislation Payload Test")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ⚠️ Architect: Paste the exact URL from your Postman 'Legislation' folder here:
TARGET_URL = "INSERT_POSTMAN_URL_HERE" 

PARAMS = {
    "sessionCode": "20261", 
    "billNumber": "HB42" 
}

if TARGET_URL == "INSERT_POSTMAN_URL_HERE":
    st.warning("⚠️ Waiting for Target URL. Please paste the Postman URL into the code (Line 11), commit to GitHub, and let the app reload.")
    st.stop()

with st.spinner("Pinging LIS Legislation API for HB42..."):
    try:
        response = requests.get(TARGET_URL, headers=HEADERS, params=PARAMS, timeout=10)
        
        if response.status_code == 200:
            st.success("✅ SUCCESS! Vault breached. Payload received:")
            st.json(response.json())
        elif response.status_code == 204:
            st.warning("⚠️ STATUS 204: The endpoint is correct, but the bill was not found or the payload is empty.")
        else:
            st.error(f"❌ ERROR: Server rejected the request. Status Code: {response.status_code}")
            st.code(response.text)

    except Exception as e:
        st.error(f"🛑 NETWORK CRASH: {e}")
