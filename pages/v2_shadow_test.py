import streamlit as st
import requests
import time

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v3 API Probe", page_icon="🕵️", layout="wide")
st.title("🕵️ v3 Probe: The 'Schedule' Endpoint")

def probe_endpoint(endpoint_name, url):
    """Generic prober for different API endpoints"""
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} # Testing House
    
    st.markdown(f"### 📡 Probing: `{endpoint_name}`")
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ Success! Found data.")
            with st.expander(f"Inspect {endpoint_name} Data"):
                st.write(data)
            return data
        else:
            st.warning(f"⚠️ {endpoint_name} returned {resp.status_code}")
    except Exception as e:
        st.error(f"💥 Error: {e}")
    return None

if st.button("🚀 Launch Probe"):
    # TEST 1: The most likely candidate
    probe_endpoint("Schedule List", "https://lis.virginia.gov/Schedule/api/getschedulelistasync")
    
    # TEST 2: Legislation Event (Often used for hearings)
    probe_endpoint("Legislation Event", "https://lis.virginia.gov/LegislationEvent/api/getlegislationeventlistasync")

    # TEST 3: Committee Meetings
    probe_endpoint("Committee Meetings", "https://lis.virginia.gov/Committee/api/getcommitteemeetinglistasync")
