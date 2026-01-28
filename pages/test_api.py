import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
# The endpoint we discovered
API_URL = "https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync"
SESSION_CODE = "20261" 

# THE MASTER KEY (Found in your screenshot)
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v132 Master Key", page_icon="🗝️", layout="wide")
st.title("🗝️ v132: The Master Key (API Authorization)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

# HEADERS (Now including the Webapikey)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://lis.virginia.gov/',
    'Webapikey': WEB_API_KEY # <--- THE MISSING LINK
}

def unlock_api(target_id_list):
    st.write(f"🔐 **Authenticating with Key:** `{WEB_API_KEY}`")
    
    found_subs = []
    
    # We'll scan a small range around H18's likely ID just in case
    # H01 is usually 1, so H18 is likely ~18-25 or ~40-50 depending on how they count Senate
    # Let's try your specific integer hunt target first (45)
    
    for test_id in target_id_list:
        url = API_URL
        params = {"sessionCode": SESSION_CODE, "id": str(test_id)}
        
        try:
            resp = session.get(url, headers=HEADERS, params=params, timeout=3)
            
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("Name", "Unknown")
                
                if name:
                    st.success(f"✅ **Connected to ID {test_id}:** {name}")
                    
                    if "SubCommittees" in data:
                        subs = data["SubCommittees"]
                        if subs:
                            st.write(f"   -> Found {len(subs)} Subcommittees")
                            for s in subs:
                                found_subs.append({
                                    "Parent": name,
                                    "Subcommittee": s.get("Name"),
                                    "GHOST ID": s.get("CommitteeId")
                                })
                        else:
                            st.caption("   -> No subcommittees.")
            elif resp.status_code == 401:
                st.error("❌ 401 Unauthorized. Key might be session-specific.")
                return
            else:
                st.warning(f"⚠️ ID {test_id}: Status {resp.status_code}")
                
        except Exception as e:
            st.error(f"Error: {e}")
            
    # RESULTS
    if found_subs:
        st.divider()
        st.subheader("🎉 The Treasure Map")
        st.table(found_subs)
        
        # PYTHON MAP
        st.markdown("### 📋 Copy this for the Final Fix:")
        code_block = "SUBCOMMITTEE_MAP = {\n"
        for item in found_subs:
            # Clean name: "Subcommittee on X" -> "X"
            safe_name = item['Subcommittee'].replace("Subcommittee", "").replace("on", "").strip()
            code_block += f'    "{safe_name}": "{item["GHOST ID"]}",\n'
        code_block += "}"
        st.code(code_block)

# --- UI ---
st.sidebar.header("🗝️ Master Key Tool")
st.sidebar.info("Using the Webapikey found in your headers.")

# We will test a range of IDs to be safe. 
# Privileges & Elections is often ID 45 or 46 in the database.
scan_range = st.sidebar.text_input("IDs to Scan (comma separated):", value="44,45,46,47,48")

if st.sidebar.button("🔴 Unlock with Master Key"):
    ids = [x.strip() for x in scan_range.split(',')]
    unlock_api(ids)
