import streamlit as st
import requests
import json
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v123 API Breaker", page_icon="🔓", layout="wide")
st.title("🔓 v123: The API Breaker")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json' # Critical for API calls
}

# --- THE HIDDEN API PROBE ---
def probe_hidden_api(committee_id):
    """
    Attempts to hit the internal API discovered in the Network tab.
    Endpoint: https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync
    """
    url = "https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync"
    params = {
        "sessionCode": SESSION_CODE,
        "committeeId": committee_id
    }
    
    st.write(f"**Attempting to breach:** `{url}`")
    st.write(f"**Payload:** `{params}`")
    
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=5)
        st.write(f"**Status Code:** `{resp.status_code}`")
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                st.success("✅ BREACH SUCCESSFUL: JSON Data Retrieved!")
                
                # Inspect for Subcommittees
                if "SubCommittees" in data:
                    subs = data["SubCommittees"]
                    st.write(f"**Found {len(subs)} Subcommittees:**")
                    
                    # Formatting for readability
                    clean_list = []
                    for sub in subs:
                        clean_list.append({
                            "Name": sub.get("Name"),
                            "CommitteeId": sub.get("CommitteeId"), # This is the secret ID!
                            "ParentId": sub.get("ParentCommitteeId")
                        })
                    st.table(clean_list)
                    return data
                else:
                    st.warning("JSON received, but 'SubCommittees' key is missing.")
                    st.json(data)
            except:
                st.error("❌ Failed to parse JSON. Response might be raw HTML.")
                st.text(resp.text[:1000])
        else:
            st.error(f"❌ Request Failed: {resp.status_code}")
            
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")

# --- UI ---
st.sidebar.header("🔓 API Breaker Tool")
st.sidebar.info("This tool tests if we can bypass the website and talk directly to the database.")

target_id = st.sidebar.text_input("Target Committee ID:", value="H18") # H18 is Privileges

if st.sidebar.button("🔴 Test Hidden API"):
    with st.spinner("Sending Probe..."):
        probe_hidden_api(target_id)

st.divider()
st.markdown("""
### What are we looking for?
If this works, we will see a list like this:
* **Name:** Subcommittee on Campaigns and Candidates
* **CommitteeId:** `H18003` (The "Ghost ID")

Once we have that ID, we can construct the perfect link:  
`.../committee-information/H18003/committee-details`
""")
