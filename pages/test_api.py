import streamlit as st
import requests
import json

# --- CONFIGURATION ---
BASE_API = "https://lis.virginia.gov/Committee/api"
SESSION_CODE = "20261" 

st.set_page_config(page_title="v126 Rosetta Stone", page_icon="🪨", layout="wide")
st.title("🪨 v126: The Rosetta Stone (Parameter Fix)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

# HEADERS (Keep these, they are working)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://lis.virginia.gov/session-details/20261/committee-information/H18/committee-details',
    'X-Requested-With': 'XMLHttpRequest'
}

# --- PROBE FUNCTION ---
def probe_api(target_id):
    # CRITICAL FIX: Changing 'committeeId' to 'id'
    url = f"{BASE_API}/getCommitteeByIdAsync"
    params = {
        "sessionCode": SESSION_CODE,
        "id": target_id  # <--- THIS IS THE FIX
    }
    
    st.markdown(f"### 📡 Sending Corrected Payload to `{url}`...")
    st.code(f"Params: {params}", language="json")
    
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=5)
        
        if resp.status_code == 200:
            st.balloons()
            st.success("✅ BREACH SUCCESSFUL!")
            data = resp.json()
            
            # PARSE THE GHOSTS
            if "SubCommittees" in data:
                subs = data["SubCommittees"]
                st.write(f"**Found {len(subs)} Subcommittees:**")
                
                clean_list = []
                for sub in subs:
                    clean_list.append({
                        "Name": sub.get("Name"),
                        "GHOST ID": sub.get("CommitteeId"), # The prize!
                        "Parent": sub.get("ParentCommitteeId")
                    })
                st.table(clean_list)
                
                # COPY PASTE BLOCK
                st.divider()
                st.write("### 📋 Copy this for the Final App:")
                code_block = "SUBCOMMITTEE_MAP = {\n"
                for item in clean_list:
                    safe_key = item['Name'].replace("Subcommittee", "").strip()
                    code_block += f'    "{safe_key}": "{item["GHOST ID"]}",\n'
                code_block += "}"
                st.code(code_block)
                
            else:
                st.warning("Response valid, but no 'SubCommittees' key found.")
                st.json(data)
                
        else:
            st.error(f"❌ Failed ({resp.status_code})")
            st.text(resp.text[:500])
            
    except Exception as e:
        st.error(f"Connection Error: {e}")

# --- UI ---
st.sidebar.header("🪨 Rosetta Tool")
target_id = st.sidebar.text_input("Target Committee ID:", value="H18")

if st.sidebar.button("🔴 Test Hidden API"):
    probe_api(target_id)
