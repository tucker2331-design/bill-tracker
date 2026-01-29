import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v701 Search & Rescue", page_icon="🛟", layout="wide")
st.title("🛟 v701: The 'Search & Rescue' Operation")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_search_rescue():
    # --- STEP 1: VERIFY SESSION CODE ---
    st.subheader("Step 1: Verifying Active Session...")
    
    # We guess the Session service name based on patterns
    s_url = f"{API_BASE}/Session/api/GetSessionListAsync"
    
    active_session = "20261" # Default fallback
    
    try:
        r = session.get(s_url, headers=headers, timeout=5)
        if r.status_code == 200:
            sessions = r.json()
            if sessions:
                # Try to find the one marked 'IsActive' or 'Current'
                # Just dumping the first one for now
                target = sessions[0]
                if isinstance(target, dict):
                     s_code = target.get("SessionCode")
                     s_desc = target.get("Description") or target.get("SessionName")
                     st.success(f"✅ API reports Session: **{s_desc}** (`{s_code}`)")
                     if s_code: active_session = s_code
            else:
                st.warning("⚠️ Session List Empty. Using default '20261'.")
        else:
            st.warning(f"⚠️ Could not verify session ({r.status_code}). Using '20261'.")
            
    except Exception as e:
        st.error(f"Session Check Error: {e}")

    # --- STEP 2: ADVANCED SEARCH PROBE ---
    st.divider()
    st.subheader(f"Step 2: Probing Advanced Search (Session: {active_session})")
    
    # We use the endpoint found in your screenshot:
    # AdvancedLegislationSearch/api/GetLegislationListAsync
    search_url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
    
    # We try a POST request with a search body
    # This is a common pattern for .NET Advanced Search APIs
    payload = {
        "SessionCode": active_session,
        "CommitteeId": 1, # Agriculture (Confirmed ID)
        "ChamberCode": "H"
    }
    
    st.write(f"🚀 POSTing to `{search_url}`")
    st.write("Payload:", payload)
    
    try:
        resp = session.post(search_url, headers=headers, json=payload, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Unwrap Logic
            bills = []
            if isinstance(data, dict):
                if "Legislation" in data: bills = data["Legislation"]
                elif "Items" in data: bills = data["Items"]
                elif "Results" in data: bills = data["Results"]
                else: 
                    st.info(f"📦 Response Keys: {list(data.keys())}")
                    
            elif isinstance(data, list):
                bills = data
                
            if bills:
                st.success(f"🎉 **PAYDIRT!** Found {len(bills)} bills via Advanced Search!")
                st.dataframe(bills[:10])
                st.balloons()
            else:
                st.warning("⚠️ 200 OK (Empty List). Search parameters might be strict.")
                st.write("Raw Response:", data)
                
        elif resp.status_code == 405:
            st.error("❌ 405 Method Not Allowed (Maybe it wants GET?)")
            # Fallback to GET
            st.write("Trying GET...")
            r_get = session.get(search_url, headers=headers, params={"sessionCode": active_session, "committeeId": 1}, timeout=5)
            if r_get.status_code == 200:
                st.success("✅ GET Worked!")
                st.json(r_get.json())
            else:
                st.error(f"❌ GET Failed: {r_get.status_code}")
                
        else:
            st.error(f"❌ Status {resp.status_code}")
            st.text(resp.text[:500])

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Search & Rescue"):
    run_search_rescue()
