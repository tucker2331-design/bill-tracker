import streamlit as st
import requests
import json

# --- CONFIGURATION ---
# 🔑 Your API Key (Rotate this after testing!)
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="API Probe", page_icon="🧪")

st.title("🧪 LIS API Connection Test")

def test_calendar_endpoint(chamber):
    url = "https://lis.virginia.gov/Calendar/api/getcalendarlistasync"
    
    headers = {
        "WebAPIKey": API_KEY,
        "Accept": "application/json"
    }
    
    params = {
        "sessionCode": SESSION_CODE,
        "chamberCode": chamber,
    }

    st.subheader(f"📡 Pinging {chamber} Calendar API...")
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ Success! Found {len(data)} calendar entries.")
            
            # Show the raw data for inspection
            with st.expander("View Raw JSON Response"):
                st.json(data)
            
            # SEARCH FOR HB1 SPECIFICALLY
            found_hb1 = False
            if isinstance(data, list):
                for entry in data:
                    # Convert everything to string to search easily
                    entry_str = str(entry).upper()
                    if "HB1" in entry_str or "HB 1" in entry_str:
                        st.balloons()
                        st.warning("🔥 FOUND HB1! The API has the data!")
                        st.write(entry)
                        found_hb1 = True
                        break
            
            if not found_hb1:
                st.info("ℹ️ HB1 was not found in this list.")
                
        elif resp.status_code == 401:
            st.error("❌ Authentication Failed. Check your API Key.")
        else:
            st.error(f"❌ Error {resp.status_code}: {resp.text}")
            
    except Exception as e:
        st.error(f"💥 Critical Error: {e}")

# --- RUN THE TEST ---
if st.button("🚀 Run Live Test"):
    test_calendar_endpoint("H") # Test House
    st.divider()
    test_calendar_endpoint("S") # Test Senate
