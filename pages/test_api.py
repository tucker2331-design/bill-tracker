import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
HB1_ID = 98525 # The Bill we are hunting

st.set_page_config(page_title="v1300 Session Matchmaker", page_icon="❤️", layout="wide")
st.title("❤️ v1300: The 'Session Matchmaker'")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_matchmaker():
    st.subheader("Step 1: Downloading All Possible Sessions...")
    
    url = f"{API_BASE}/Session/api/GetSessionListAsync"
    try:
        resp = session.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            st.error("❌ Failed to get sessions.")
            return
            
        data = resp.json()
        all_sessions = []
        
        # Unwrap
        if isinstance(data, dict):
            all_sessions = data.get("Sessions", [])
        elif isinstance(data, list):
            all_sessions = data
            
        # Filter for recent years to save time (2024-2026)
        recent_sessions = [
            s for s in all_sessions 
            if s.get("SessionYear") in [2024, 2025, 2026]
        ]
        
        if not recent_sessions:
            st.warning("No recent sessions found. Testing ALL sessions.")
            recent_sessions = all_sessions[:10] # Cap at 10 to avoid timeout
            
        st.success(f"✅ Found {len(recent_sessions)} candidates.")
        
        # --- STEP 2: THE MATCHMAKER LOOP ---
        target_url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDsAsync"
        
        for s in recent_sessions:
            s_code = s.get("SessionCode")
            s_name = s.get("DisplayName") or s.get("Description")
            
            # Use the payload format that gave us 204 (Valid Syntax)
            # We try passing sessionCode in BOTH URL and BODY just to be sure
            payload = {"ids": [HB1_ID], "sessionCode": s_code}
            params = {"sessionCode": s_code}
            
            st.caption(f"Trying Session: **{s_code}** ({s_name})...")
            
            try:
                # We use the 'Shot B' technique from v1202 which was most promising
                r = session.post(target_url, headers=headers, params=params, json=payload, timeout=2)
                
                if r.status_code == 200:
                    data = r.json()
                    
                    # Check if empty list
                    items = []
                    if isinstance(data, dict): items = data.get("Legislation") or data.get("Items") or []
                    elif isinstance(data, list): items = data
                    
                    if items:
                        st.success(f"🎉 **MATCH FOUND!** Bill {HB1_ID} belongs to Session `{s_code}`!")
                        st.json(items[0])
                        st.balloons()
                        return # STOP WE WON
                        
                elif r.status_code == 400:
                     st.write(f"❌ {s_code}: 400 Bad Request")
                     
            except Exception:
                pass
                
        st.error("❌ Checked all recent sessions. None matched Bill 98525.")
        
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Matchmaker"):
    run_matchmaker()
