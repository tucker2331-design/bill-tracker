import streamlit as st
import requests
import json

st.set_page_config(page_title="LIS API JSON Probe", layout="wide")

st.title("🚀 Enterprise LIS API JSON Probe")
st.markdown("Testing the modern REST endpoints to extract structured Calendar and Schedule data.")

# Your official WebAPIKey from the backend worker
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# 1. Input UI for the specific Postman Endpoint
st.subheader("1. Target Endpoint")
st.info("Paste the exact URL from your Postman collection for the Calendar, Schedule, or LegislationEvent endpoint.")

endpoint_url = st.text_input(
    "API URL:", 
    value="https://lis.virginia.gov/api/v1/schedule/getscheduleasync",
    help="Example: https://lis.virginia.gov/api/v1/schedule/getscheduleasync"
)

# 2. Parameters UI (To handle the 261 vs 20261 shortcode trap)
col1, col2 = st.columns(2)
with col1:
    session_code = st.text_input("Session Parameter (e.g., sessionCode):", value="261")
with col2:
    extra_params = st.text_input("Other Parameters (e.g. committeeId=H01):", value="")

# 3. The Execution Engine
if st.button("📡 Execute API Call", type="primary"):
    with st.spinner("Pinging state servers..."):
        try:
            # Construct parameters safely
            params = {}
            if session_code:
                params["sessionCode"] = session_code 
            
            if extra_params:
                # Basic string parsing for simple testing (key=value)
                for pair in extra_params.split("&"):
                    if "=" in pair:
                        k, v = pair.split("=")
                        params[k] = v

            # Fire the request
            response = requests.get(endpoint_url, headers=HEADERS, params=params, timeout=10)
            
            # Check for the HTML Error Trap
            if "text/html" in response.headers.get("Content-Type", ""):
                st.error(f"🚨 TRAP TRIGGERED: The server returned an HTML error page instead of JSON. Status Code: {response.status_code}")
                with st.expander("View Raw HTML Response"):
                    st.code(response.text[:2000]) # Show first 2000 chars of error
            else:
                response.raise_for_status()
                data = response.json()
                
                st.success(f"✅ SUCCESS! Status Code: {response.status_code}")
                
                # 4. Payload Visualization
                st.subheader("2. JSON Payload Map")
                
                # Try to find the list of items if it's wrapped in a parent key
                data_keys = list(data.keys()) if isinstance(data, dict) else []
                st.write(f"**Root Keys Detected:** `{data_keys}`")
                
                # Find the actual array of data to preview it cleanly
                data_list = []
                for key in data_keys:
                    if isinstance(data[key], list):
                        data_list = data[key]
                        break
                
                if data_list:
                    st.write(f"**Found {len(data_list)} items in the array.** Here is the first item's structure:")
                    st.json(data_list[0])
                else:
                    st.write("**Raw JSON Structure:**")
                    st.json(data)
                
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection Error: {e}")
        except json.JSONDecodeError:
            st.error("❌ Parsing Error: The response was not valid JSON.")
            st.code(response.text[:2000])
