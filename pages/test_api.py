import streamlit as st
import requests
import concurrent.futures
import time

# --- CONFIGURATION ---
BASE_API = "https://lis.virginia.gov/Committee/api"
SESSION_CODE = "20261" 

st.set_page_config(page_title="v127 Integer Hunt", page_icon="🔢", layout="wide")
st.title("🔢 v127: The Integer Hunt (Brute Force Scan)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Referer': 'https://lis.virginia.gov/',
    'X-Requested-With': 'XMLHttpRequest'
}

# --- 1. THE SCANNER ---
def check_id(numeric_id):
    url = f"{BASE_API}/getCommitteeByIdAsync"
    params = {"sessionCode": SESSION_CODE, "id": str(numeric_id)}
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if "Name" in data and data["Name"]:
                return (numeric_id, data["Name"], len(data.get("SubCommittees", [])))
    except:
        pass
    return None

# --- 2. THE PROBE (For specific ID) ---
def probe_specific_id(target_id):
    url = f"{BASE_API}/getCommitteeByIdAsync"
    params = {"sessionCode": SESSION_CODE, "id": target_id}
    
    st.write(f"📡 Pinging ID `{target_id}`...")
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ FOUND: {data.get('Name')}")
            
            if "SubCommittees" in data:
                subs = data["SubCommittees"]
                st.write(f"**Subcommittees ({len(subs)}):**")
                st.table([{
                    "Name": s["Name"], 
                    "GHOST ID": s["CommitteeId"], 
                    "Parent ID": s["ParentCommitteeId"]
                } for s in subs])
            else:
                st.warning("No subcommittees found.")
        else:
            st.error(f"❌ Failed: {resp.status_code}")
            st.text(resp.text)
    except Exception as e:
        st.error(f"Error: {e}")

# --- UI ---
st.sidebar.header("🔢 Integer Hunt")

# Mode 1: Test Specific
target_id = st.sidebar.text_input("Target Integer ID:", value="45")
if st.sidebar.button("Test Hidden API"):
    probe_specific_id(target_id)

st.sidebar.divider()

# Mode 2: Brute Force
if st.sidebar.button("🔴 Start Brute Force Scan (1-100)"):
    found_items = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.container(border=True):
        st.write("scanning...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Create futures
            futures = {executor.submit(check_id, i): i for i in range(1, 101)}
            
            completed = 0
            for f in concurrent.futures.as_completed(futures):
                completed += 1
                progress_bar.progress(completed / 100)
                
                result = f.result()
                if result:
                    found_items.append(result)
                    # Sort by ID for cleaner display
                    found_items.sort(key=lambda x: x[0])
                    
                    # Live Update Table
                    status_text.dataframe(
                        [{"ID": r[0], "Name": r[1], "Subs": r[2]} for r in found_items],
                        use_container_width=True
                    )
    
    st.success("Scan Complete!")
