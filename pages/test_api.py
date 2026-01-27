import streamlit as st
import requests
import concurrent.futures
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
SESSION_CODE = "20261" 
BASE_URL = "https://lis.virginia.gov/session-details"

st.set_page_config(page_title="v115 Calibration", page_icon="🎛️", layout="wide")
st.title("🎛️ v115: The Calibration Tool")
st.markdown("""
**The Problem:** The "Room Numbers" (IDs) for committees have changed.  
**The Fix:** This tool pings every room number (H01-H25, S01-S15) to see who is inside.
""")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def scan_committee_id(chamber, num):
    """
    Pings a specific ID (e.g., H01) and scrapes the Committee Name.
    """
    id_str = f"{chamber}{num:02d}"
    url = f"{BASE_URL}/{SESSION_CODE}/committee-information/{id_str}/committee-details"
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # LIS usually puts the name in a specific <h3> or <h4> tag, or the <title>
            # Method 1: Check Page Title (cleanest)
            page_title = soup.title.string if soup.title else ""
            
            # Method 2: Look for the big header inside the page
            header = soup.find('h3') # LIS uses H3 for committee names often
            header_text = header.get_text(strip=True) if header else ""
            
            # Cleanup Name
            name = header_text if header_text else page_title
            name = name.replace(" - 2026 Regular Session - Virginia LIS", "")
            name = name.replace("Membership", "").strip()
            
            if name and "Error" not in name:
                return (id_str, name, url)
    except:
        pass
    return None

# --- MAIN UI ---
st.sidebar.header("Calibration Controls")

if st.sidebar.button("🔴 Run Calibration Scan"):
    found_committees = []
    
    # SCANNING HOUSE (H01 - H25)
    with st.status("Scanning House Committees (H01-H25)..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scan_committee_id, "H", i) for i in range(1, 26)]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res: found_committees.append(res)
    
    # SCANNING SENATE (S01 - S15)
    with st.status("Scanning Senate Committees (S01-S15)..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scan_committee_id, "S", i) for i in range(1, 16)]
            for f in concurrent.futures.as_completed(futures):
                res = f.result()
                if res: found_committees.append(res)
                
    # DISPLAY RESULTS
    st.success(f"Scan Complete! Found {len(found_committees)} active committees.")
    
    # Sort by ID
    found_committees.sort(key=lambda x: x[0])
    
    st.divider()
    st.subheader("📋 The Truth Table")
    st.markdown("Please copy/paste this list back to me so I can update the Master Map.")
    
    # Create clean Dictionary text for copy-paste
    code_block = "NEW_COMMITTEE_MAP = {\n"
    for cid, name, url in found_committees:
        clean_name = name.replace('"', '').strip()
        code_block += f'    "{cid}": "{clean_name}",\n'
    code_block += "}"
    
    st.code(code_block, language="python")
    
    # Visual Table
    st.table([{"ID": c[0], "Name": c[1]} for c in found_committees])

else:
    st.info("Click the button in the sidebar to start the discovery process.")
