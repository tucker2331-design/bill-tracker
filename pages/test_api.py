import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v803 Iteration Fix", page_icon="🛠️", layout="wide")
st.title("🛠️ v803: The Iteration Fix (Session 59)")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_fix():
    st.subheader("Step 1: Finding Session #59 (Correctly)...")
    
    url = f"{API_BASE}/Session/api/GetSessionListAsync"
    target_code = None
    
    try:
        resp = session.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            raw_data = resp.json()
            
            # --- THE FIX: UNWRAP CORRECTLY ---
            # If it's a dict like {"Sessions": [...]}, get the list inside.
            all_sessions = []
            if isinstance(raw_data, dict):
                all_sessions = raw_data.get("Sessions", [])
            elif isinstance(raw_data, list):
                all_sessions = raw_data
                
            if not all_sessions:
                st.error("❌ Unwrapped list is empty.")
                st.write("Raw Data:", raw_data)
                return

            # Now we can safely search for ID 59
            target = next((s for s in all_sessions if s.get("SessionID") == 59), None)
            
            if target:
                target_code = target.get("SessionCode")
                desc = target.get("Description") or target.get("DisplayName")
                st.success(f"✅ FOUND IT! Session 59 is **'{desc}'**")
                st.info(f"🔑 The Magic Code is: `{target_code}`")
                
                # Show the object to verify we have the right one
                with st.expander("View Session Details"):
                    st.json(target)
            else:
                st.error("❌ Session 59 not found in the list.")
                return
        else:
            st.error(f"❌ Session API Failed: {resp.status_code}")
            return

        # --- STEP 2: USE THE CODE ---
        if target_code:
            st.divider()
            st.subheader(f"Step 2: Unlocking Committee 1 with Code `{target_code}`")
            
            search_url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
            
            payload = {
                "SessionCode": target_code,
                "CommitteeId": 1, # Agriculture (Confirmed ID)
                "ChamberCode": "H"
            }
            
            st.write(f"🚀 POSTing payload...", payload)
            
            r2 = session.post(search_url, headers=headers, json=payload, timeout=5)
            
            if r2.status_code == 200:
                data = r2.json()
                
                # Unwrap Logic again just to be safe
                bills = []
                if isinstance(data, dict):
                     if "Legislation" in data: bills = data["Legislation"]
                     elif "Items" in data: bills = data["Items"]
                     elif "Results" in data: bills = data["Results"]
                elif isinstance(data, list):
                    bills = data
                
                if bills:
                    st.success(f"🎉 **PAYDIRT!** Found {len(bills)} bills!")
                    st.dataframe(bills[:15])
                    st.balloons()
                else:
                    st.warning("⚠️ 200 OK (Empty List).")
                    st.write("Raw Response:", data)
            else:
                st.error(f"❌ Search Failed: {r2.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Fix"):
    run_fix()
