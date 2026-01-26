import streamlit as st
import requests
import json
import pandas as pd

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v102 Anatomy", page_icon="🧬", layout="wide")
st.title("🧬 v102: Schedule Anatomy (Raw Data Inspection)")
st.markdown("Inspecting the **Schedules** object from the successful API call to find hidden fields.")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# --- FETCH FUNCTION ---
@st.cache_data(ttl=600)
def fetch_raw_schedule_sample():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} 
    
    try:
        st.write(f"📡 Requesting: `{url}`")
        resp = session.get(url, headers=HEADERS, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("Schedules", [])
            st.success(f"✅ Success! Received {len(items)} items.")
            return items
        else:
            st.error(f"❌ Failed: {resp.status_code}")
            st.text(resp.text)
            return []
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return []

# --- MAIN DISPLAY ---

items = fetch_raw_schedule_sample()

if items:
    st.divider()
    
    # 1. SUMMARY TABLE (First 10 items)
    st.subheader("1. Data Overview (First 5 Items)")
    df = pd.DataFrame(items[:5])
    st.dataframe(df)
    
    st.divider()

    # 2. DEEP DIVE (Raw JSON)
    st.subheader("2. Deep Dive: Item Anatomy")
    st.info("Look closely at these fields. Do you see a 'CommitteeID' or 'Link'?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Sample A (Item 0)")
        if len(items) > 0:
            st.json(items[0], expanded=True)
            
    with col2:
        st.markdown("### Sample B (Item 5)")
        if len(items) > 5:
            st.json(items[5], expanded=True)

    # 3. LINK CHECKER
    st.divider()
    st.subheader("3. Hidden Links Check")
    st.markdown("Scanning all items for 'http' in the `Description` field...")
    
    count = 0
    for i, item in enumerate(items):
        desc = item.get("Description", "")
        if desc and "http" in str(desc):
            st.markdown(f"**Found in Item {i} ({item.get('OwnerName')}):**")
            st.code(desc, language="html")
            count += 1
            if count >= 5: break
    
    if count == 0:
        st.warning("No 'http' links found in Descriptions.")
