import streamlit as st
import requests
import json
import pandas as pd

# --- CONFIGURATION ---
BASE_API = "https://lis.virginia.gov/Committee/api"
SESSION_CODE = "20261" 

st.set_page_config(page_title="v125 The Mimic", page_icon="🎭", layout="wide")
st.title("🎭 v125: The Mimic (Header Spoofing)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

# 🎭 THE MASQUERADE HEADERS
# We must look exactly like a browser's background request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://lis.virginia.gov/session-details/20261/committee-information/H18/committee-details',
    'X-Requested-With': 'XMLHttpRequest', # Critical for .NET MVC apps
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
}

# --- PROBE FUNCTION ---
def probe_api(target_id):
    results = []
    
    # --- ATTEMPT 1: Get Specific Committee (The one we saw) ---
    url1 = f"{BASE_API}/getCommitteeByIdAsync"
    params1 = {"sessionCode": SESSION_CODE, "committeeId": target_id}
    
    st.write(f"🔹 **Attempt 1:** GET `{url1}`")
    try:
        r1 = session.get(url1, headers=HEADERS, params=params1, timeout=5)
        if r1.status_code == 200:
            st.success("✅ SUCCESS!")
            return parse_success(r1.json())
        else:
            st.warning(f"Failed ({r1.status_code}). Server said: {r1.text[:100]}")
    except Exception as e:
        st.error(f"Error: {e}")

    # --- ATTEMPT 2: Get ALL Committees (Backup Plan) ---
    # If the specific one is locked, maybe the master list is open?
    st.divider()
    url2 = f"{BASE_API}/getCommitteesAsync"
    params2 = {"sessionCode": SESSION_CODE}
    
    st.write(f"🔹 **Attempt 2:** GET `{url2}` (The Master List)")
    try:
        r2 = session.get(url2, headers=HEADERS, params=params2, timeout=5)
        if r2.status_code == 200:
            st.success("✅ MASTER LIST RETRIEVED!")
            # We have to dig through the master list to find our subcommittees
            data = r2.json()
            if isinstance(data, list):
                # Filter for ones that have our target as a Parent
                subs = [x for x in data if x.get("ParentCommitteeId") == target_id]
                if subs:
                    st.success(f"Found {len(subs)} subcommittees in Master List!")
                    return show_table(subs)
                else:
                    st.warning("Master list loaded, but no subcommittees found for this parent ID.")
            return
        else:
            st.error(f"Failed ({r2.status_code})")
    except Exception as e:
        st.error(f"Error: {e}")

def parse_success(data):
    # Check if subcommittees are nested
    if "SubCommittees" in data:
        subs = data["SubCommittees"]
        if subs:
            st.balloons()
            st.success(f"🎉 FOUND {len(subs)} GHOSTS!")
            show_table(subs)
        else:
            st.warning("Request worked, but 'SubCommittees' list is empty.")
            st.json(data)
    else:
        st.warning("JSON Valid, but unexpected structure:")
        st.json(data)

def show_table(subs):
    clean = []
    for s in subs:
        clean.append({
            "Name": s.get("Name"),
            "GHOST ID": s.get("CommitteeId"),
            "Chamber": s.get("ChamberCode")
        })
    st.table(clean)
    
    # CODE GEN ASSIST
    st.divider()
    st.markdown("### 📋 Copy this Map!")
    code_block = "SUBCOMMITTEE_MAP = {\n"
    for item in clean:
        safe_key = item['Name'].replace("Subcommittee", "").strip()
        code_block += f'    "{safe_key}": "{item["GHOST ID"]}",\n'
    code_block += "}"
    st.code(code_block)

# --- UI ---
st.sidebar.header("🎭 The Mimic")
target_id = st.sidebar.text_input("Target Committee ID:", value="H18")

if st.sidebar.button("🔴 Test Hidden API"):
    probe_api(target_id)
