import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="API Parameter Cracker", layout="wide")

st.title("🚀 LIS API Parameter Cracker")
st.markdown("Brute-forcing the undocumented Virginia General Assembly docket endpoints...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
TARGET_URL = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"

# Generate the test combinations
test_combinations = []
for sess in ["261", "20261"]:
    for comm in ["H02", "02", "2"]:
        # Test with Chamber Code Explicitly set to H
        test_combinations.append({"sessionCode": sess, "chamberCode": "H", "committeeNumber": comm})
        # Test without Chamber Code (sometimes they only want the committee ID)
        test_combinations.append({"sessionCode": sess, "committeeID": comm})
        test_combinations.append({"sessionCode": sess, "committeeId": comm}) # Test lowercase 'd'

if st.button("📡 Start API Cracker", type="primary"):
    cracked = False
    
    # Create an empty placeholder to show live progress without cluttering the screen
    progress_text = st.empty()
    
    for i, params in enumerate(test_combinations):
        progress_text.info(f"**Testing Combination {i+1}/{len(test_combinations)}:** Firing payload `{params}`...")
        
        try:
            response = requests.get(TARGET_URL, headers=HEADERS, params=params, timeout=5)
            
            if "text/html" in response.headers.get("Content-Type", ""):
                st.warning(f"❌ **Attempt {i+1} Failed:** Server threw HTML trap (Status {response.status_code}) | Params: {params}")
            
            elif response.status_code == 200:
                progress_text.empty() # Clear the progress text
                st.success("✅ **LOCK CRACKED! STATUS 200 OK**")
                st.divider()
                
                st.subheader("🔑 Winning Parameters")
                st.code(params)
                
                st.subheader("🔗 Exact URL Fired")
                st.code(response.url)
                
                st.subheader("📦 JSON Payload")
                data = response.json()
                st.json(data)
                
                cracked = True
                break
                
            else:
                st.error(f"❌ **Attempt {i+1} Failed:** Status {response.status_code} | Params: {params}")
                
        except Exception as e:
            st.error(f"⚠️ **Attempt {i+1} Error:** Connection Failed - {e}")
            
        time.sleep(0.5) # Slight pause to not overwhelm the state server

    if not cracked:
        st.error("💀 **ALL TESTS FAILED.** The endpoint is locked behind an undocumented parameter. We proceed to the Hybrid Architecture.")
