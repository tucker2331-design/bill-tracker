import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
HB1_ID = 98525 # From your v800 screenshot

st.set_page_config(page_title="v1000 Ghostbuster", page_icon="🚫", layout="wide")
st.title("🚫 v1000: The 'Ghostbuster' Protocol")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_ghostbuster():
    # --- PROBE 1: HB1 HISTORY ---
    st.subheader(f"Step 1: Checking History for HB1 (ID: {HB1_ID})...")
    # Endpoint from Heist list
    hist_url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
    
    try:
        # Try GET
        r = session.get(hist_url, headers=headers, params={"legislationId": HB1_ID}, timeout=5)
        if r.status_code == 200:
            history = r.json()
            if history:
                st.success(f"✅ HB1 History Found! ({len(history)} items)")
                st.dataframe(history)
                # Check for Committee keywords
                for h in history:
                    desc = h.get("Description", "").lower()
                    if "referred" in desc or "committee" in desc:
                        st.info(f"📍 Clue: {h.get('Description')}")
            else:
                st.warning("⚠️ HB1 exists, but History is empty.")
        else:
            st.error(f"❌ History Failed: {r.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")

    # --- PROBE 2: THE "SESSION LIST" ---
    st.divider()
    st.subheader("Step 2: Trying 'getLegislationSessionListAsync'...")
    # Note the lowercase 'g' from screenshot
    list_url = f"{API_BASE}/Legislation/api/getLegislationSessionListAsync"
    
    try:
        # Try GET with sessionCode
        r2 = session.get(list_url, headers=headers, params={"sessionCode": SESSION_CODE}, timeout=10)
        
        if r2.status_code == 200:
            data = r2.json()
            # Unwrap
            bills = []
            if isinstance(data, list): bills = data
            elif isinstance(data, dict):
                bills = data.get("Legislation") or data.get("Items") or []
            
            if bills:
                st.success(f"🎉 **JACKPOT!** Found {len(bills)} bills for the session!")
                st.dataframe(bills[:10])
                st.balloons()
            else:
                st.warning("⚠️ 200 OK (Empty List). Endpoint works, but returned nothing.")
        else:
            st.error(f"❌ List Failed: {r2.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

    # --- PROBE 3: THE "ID LIST" (BACKUP) ---
    st.divider()
    st.subheader("Step 3: Trying 'GetLegislationIdsListAsync'...")
    id_url = f"{API_BASE}/Legislation/api/GetLegislationIdsListAsync"
    
    try:
        r3 = session.get(id_url, headers=headers, params={"sessionCode": SESSION_CODE}, timeout=10)
        if r3.status_code == 200:
            ids = r3.json()
            if ids:
                st.success(f"✅ Found {len(ids)} Bill IDs!")
                st.write("First 10 IDs:", ids[:10])
            else:
                st.warning("⚠️ 200 OK (Empty ID List).")
        else:
            st.error(f"❌ ID List Failed: {r3.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Ghostbuster"):
    run_ghostbuster()
