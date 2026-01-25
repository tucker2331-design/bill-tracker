import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
BASE_URL = "https://lis.virginia.gov"

st.set_page_config(page_title="LIS API Explorer", layout="wide")
st.title("🕵️‍♂️ LIS API Explorer")
st.markdown("""
**The Theory:** The "Schedule" API is for committees. The **"Calendar"** or **"Session"** API is for the Floor.
Use this tool to find the specific endpoint that contains the "Convening Time".
""")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("🔌 Connection Settings")
service = st.sidebar.selectbox("1. Select Service", ["Calendar", "Session", "LegislationEvent", "Schedule"])

# Common method patterns in LIS
method_guess = st.sidebar.selectbox(
    "2. Select/Type Method", 
    [
        "getcalendarlist", 
        "getdailycalendar", 
        "getsessionlist", 
        "getsessioninfo",
        "geteventlist",
        "getschedulelistasync" # The one we know works
    ]
)
custom_method = st.sidebar.text_input("Or type custom method (from docs):", "")
final_method = custom_method if custom_method else method_guess

chamber = st.sidebar.radio("3. Chamber", ["H", "S"], horizontal=True)

# --- BUILD URL ---
# Note: Some LIS APIs use /api/Method, others might be different. 
# We assume the standard pattern: https://lis.virginia.gov/[Service]/api/[Method]
api_url = f"{BASE_URL}/{service}/api/{final_method}"

st.subheader(f"Target: `{api_url}`")

if st.button("🚀 Launch Probe"):
    headers = {
        "WebAPIKey": API_KEY, 
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    
    # Standard LIS Parameters
    params = {
        "sessionCode": SESSION_CODE,
        "chamberCode": chamber,
        "date": datetime.now().strftime("%Y-%m-%d") # Some endpoints need a date
    }
    
    try:
        st.info(f"Sending request to {service}...")
        resp = requests.get(api_url, headers=headers, params=params, timeout=10)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                st.success("✅ Connection Successful!")
                
                # METADATA SCANNER
                # We search the JSON for any key that looks like "Time"
                st.markdown("### 🔍 JSON X-Ray")
                st.caption("Searching response for 'Time', 'Convene', or 'Start'...")
                
                found_keys = []
                def find_keys(obj, path=""):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if any(x in k.lower() for x in ["time", "start", "convene"]):
                                found_keys.append(f"{path}.{k} = {v}")
                            find_keys(v, path + "." + k)
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            find_keys(item, f"{path}[{i}]")
                
                find_keys(data)
                
                if found_keys:
                    st.warning(f"Found {len(found_keys)} potential timestamps!")
                    for k in found_keys:
                        st.code(k)
                else:
                    st.info("No obvious time fields found in the keys.")

                with st.expander("📂 View Full Raw JSON", expanded=True):
                    st.json(data)
                    
            except:
                st.warning("Response was not JSON. (Might be HTML/Text)")
                st.code(resp.text[:2000])
        else:
            st.error(f"❌ Error {resp.status_code}")
            st.text(resp.text)
            
    except Exception as e:
        st.error(f"Connection Failed: {e}")

st.markdown("---")
st.info("💡 **Tip:** If `getcalendarlist` fails, check the documentation link in your screenshot for the exact method name under the 'Calendar' section.")
