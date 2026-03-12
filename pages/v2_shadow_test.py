import streamlit as st
import requests

st.set_page_config(page_title="Phase 1: REST API", layout="wide")
st.title("🚀 Step 1: Mastermind API Extraction Test")

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {
    "WebAPIKey": API_KEY, 
    "Accept": "application/json"
}

# The exact endpoint you extracted from Postman
TARGET_URL = "https://lis.virginia.gov/Legislation/api/getlegislationsessionlistasync"

# We know 20261 is the session code. We will test if omitting the hidden sessionID works.
PARAMS = {
    "sessionCode": "20261" 
}

st.markdown("This script tests our ability to pull universal JSON data directly from the state's backend, bypassing the old CSV blob methods.")

if st.button("🔥 Execute Vault Breach (Fetch Session JSON)"):
    with st.spinner("Pinging Virginia Master REST API..."):
        try:
            response = requests.get(TARGET_URL, headers=HEADERS, params=PARAMS, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                st.success("✅ SUCCESS! Database connected. Payload received:")
                
                # The API usually wraps arrays in a "ListItems" key. We handle both cases.
                items = data.get("ListItems", data) if isinstance(data, dict) else data
                
                if isinstance(items, list):
                    st.info(f"Total Bills Found in 2026 Session Database: {len(items)}")
                    st.write("### Schema Blueprint (First 2 Bills):")
                    # We only print the first two bills to prevent Streamlit from freezing
                    st.json(items[:2]) 
                else:
                    st.warning("Payload received, but it is not formatted as a standard list. Raw data:")
                    st.json(data)
                    
            elif response.status_code == 204:
                st.warning("⚠️ STATUS 204: The server accepted the request but returned no data. (We may need to find the specific 'sessionID' integer to pair with '20261').")
            else:
                st.error(f"❌ ERROR: Server rejected the request. Status Code: {response.status_code}")
                st.code(response.text)

        except Exception as e:
            st.error(f"🛑 NETWORK CRASH: {e}")
