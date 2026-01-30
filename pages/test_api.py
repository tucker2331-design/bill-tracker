import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v1400 Control Group", page_icon="⚖️", layout="wide")
st.title("⚖️ v1400: The 'Control Group' Test")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def fetch_bill_version(session_code, bill_number, label):
    url = f"{API_BASE}/LegislationVersion/api/GetLegislationVersionByBillNumberAsync"
    params = {"sessionCode": session_code, "billNumber": bill_number}
    
    st.write(f"🔎 **Fetching {label}** ({bill_number} / {session_code})...")
    
    try:
        r = session.get(url, headers=headers, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # Unwrap
            items = []
            if isinstance(data, dict): items = data.get("LegislationsVersion", [])
            elif isinstance(data, list): items = data
            
            if items:
                # Get the most recent version (usually the last in the list, or we sort)
                # actually usually the first one returned is the latest draft
                top = items[0]
                
                st.success(f"✅ {label}: Found ID {top.get('LegislationID')}")
                
                # DISPLAY KEY DATA
                c1, c2 = st.columns(2)
                with c1:
                    st.info(f"📜 **Status:** {top.get('Version')}")
                    st.caption(f"Description: {top.get('Description')}")
                with c2:
                    st.write(f"Draft Date: {top.get('DraftDate')}")
                    # Does the version object contain committee hints?
                    # We print the whole thing to check
                    with st.expander("Inspect JSON"):
                        st.json(top)
            else:
                st.warning(f"⚠️ {label}: 200 OK (Empty List)")
        else:
            st.error(f"❌ {label}: Failed {r.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")

def run_control_group():
    # TEST 1: The "Ghost" (2026 HB1)
    # Session 20261 (Regular Session 2026)
    fetch_bill_version("20261", "HB1", "The Ghost (2026)")
    
    st.divider()
    
    # TEST 2: The "Control" (2024 HB1)
    # Session 20241 (Regular Session 2024) - A known historic session
    fetch_bill_version("20241", "HB1", "The Control (2024)")

if st.button("🔴 Run Control Test"):
    run_control_group()
