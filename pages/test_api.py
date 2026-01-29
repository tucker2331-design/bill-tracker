import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v802 Chain of Custody", page_icon="🔗", layout="wide")
st.title("🔗 v802: The Chain of Custody (ID 59)")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_chain_of_custody():
    st.subheader("Step 1: Finding Session #59...")
    
    url = f"{API_BASE}/Session/api/GetSessionListAsync"
    target_code = None
    
    try:
        resp = session.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            all_sessions = resp.json()
            
            # --- THE SEARCH ---
            # We are looking for SessionID == 59 (from your HB1 screenshot)
            target = next((s for s in all_sessions if s.get("SessionID") == 59), None)
            
            if target:
                target_code = target.get("SessionCode")
                desc = target.get("Description") or target.get("DisplayName")
                st.success(f"✅ FOUND IT! Session 59 is **'{desc}'**")
                st.info(f"🔑 The Magic Code is: `{target_code}`")
                st.json(target)
            else:
                st.error("❌ Session 59 not found in the master list. (Is the list incomplete?)")
                # Fallback: Print the last 3 sessions just in case
                st.write("Last 3 Sessions on file:", all_sessions[-3:])
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
                
                # Unwrap
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
                    st.warning("⚠️ 200 OK (Empty List). Session is valid, but maybe Committee 1 is empty?")
                    st.write("Raw Response:", data)
                    
            else:
                st.error(f"❌ Search Failed: {r2.status_code}")
                st.text(r2.text[:500])

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Chain of Custody"):
    run_chain_of_custody()
