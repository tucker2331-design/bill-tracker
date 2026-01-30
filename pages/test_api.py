import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# ID from your v1400 Screenshot for 2024 HB1
HB1_2024_ID = 91072 
HB1_2026_ID = 98525

st.set_page_config(page_title="v1500 History Control", page_icon="📜", layout="wide")
st.title("📜 v1500: The History Control Test")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def check_history(bill_id, label, session_code):
    url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
    
    st.subheader(f"Testing {label} (ID: {bill_id})...")
    
    # We use the standard POST payload that usually works for .NET
    # Trying PascalCase first as per standard
    payload = {
        "LegislationId": bill_id,
        "SessionCode": session_code
    }
    
    try:
        r = session.post(url, headers=headers, json=payload, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            # Unwrap
            items = []
            if isinstance(data, dict): items = data.get("LegislationHistory") or data.get("Items") or []
            elif isinstance(data, list): items = data
            
            if items:
                st.success(f"✅ {label}: History Found! ({len(items)} events)")
                st.dataframe(items)
                
                # Check for "Referred" event
                referred = next((x for x in items if "referred" in str(x.get("Description", "")).lower()), None)
                if referred:
                    st.info(f"📍 **Committee Found in History:** {referred.get('Description')}")
                else:
                    st.warning("History found, but no 'Referred' event (yet).")
            else:
                st.warning(f"⚠️ {label}: 200 OK (Empty List)")
                
        elif r.status_code == 204:
            st.warning(f"⚪ {label}: 204 No Content (Valid request, no history exists)")
        else:
            st.error(f"❌ {label}: Failed {r.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

def run_history_control():
    # TEST 1: The Control (2024 HB1) - SHOULD HAVE HISTORY
    check_history(HB1_2024_ID, "2024 HB1 (Control)", "20241")
    
    st.divider()
    
    # TEST 2: The Ghost (2026 HB1) - MIGHT BE EMPTY
    check_history(HB1_2026_ID, "2026 HB1 (Ghost)", "20261")

if st.button("🔴 Run History Control"):
    run_history_control()
