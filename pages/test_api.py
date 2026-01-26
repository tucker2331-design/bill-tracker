import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" # 2026 Regular Session

st.set_page_config(page_title="v101 API Autopsy", page_icon="🧪", layout="wide")
st.title("🧪 v101: API Autopsy")
st.markdown("We are probing the endpoints to see exactly which one contains the **Bill-to-Committee** link.")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}

def probe_endpoint(name, url, params):
    st.header(f"📡 Probe: {name}")
    st.markdown(f"`{url}`")
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=10)
        st.write(f"**Status:** `{resp.status_code}`")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                
                # Try to find the list inside the response
                items = []
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # Look for keys that might contain lists
                    keys = list(data.keys())
                    st.write(f"**Root Keys:** {keys}")
                    for k in keys:
                        if isinstance(data[k], list):
                            items = data[k]
                            st.success(f"✅ Found {len(items)} items in key `'{k}'`")
                            break
                
                if items:
                    # Show the first item in full so we can see the fields
                    st.json(items[0], expanded=False)
                    
                    # If Probe C, check for Bill Numbers
                    if "Legislation" in name or "Referral" in name:
                        df = pd.DataFrame(items)
                        st.dataframe(df.head(5))
                else:
                    st.warning("⚠️ Response was valid JSON but empty.")
                    st.json(data)
                    
            except Exception as e:
                st.error(f"JSON Parse Error: {e}")
                st.text(resp.text[:500])
        else:
            st.error("Request Failed")
            st.text(resp.text)
            
    except Exception as e:
        st.error(f"Connection Error: {e}")
    
    st.divider()

# --- EXECUTE PROBES ---

# 1. PROBE A: Why did v99 fail?
# Maybe "chamberCode" needs to be excluded to get all?
probe_endpoint(
    "Committee List (getcommitteelist)",
    "https://lis.virginia.gov/Committee/api/getcommitteelist",
    {"sessionCode": SESSION_CODE, "chamberCode": "H"} 
)

# 2. PROBE B: Legislation
probe_endpoint(
    "Legislation List (getlegislationlist)",
    "https://lis.virginia.gov/Legislation/api/getlegislationlist",
    {"sessionCode": SESSION_CODE} 
)

# 3. PROBE C: The Potential Gold Mine
# Does this link Committees to Bills directly?
probe_endpoint(
    "Committee Referral (getcommitteelegislationreferrallist)",
    "https://lis.virginia.gov/CommitteeLegislationReferral/api/getcommitteelegislationreferrallist",
    {"sessionCode": SESSION_CODE, "chamberCode": "H"}
)

# 4. PROBE D: Schedule (Control)
probe_endpoint(
    "Schedule (getschedulelist)",
    "https://lis.virginia.gov/Schedule/api/getschedulelistasync",
    {"sessionCode": SESSION_CODE, "chamberCode": "H"}
)
