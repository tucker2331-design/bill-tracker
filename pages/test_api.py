import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
CGI_BASE = "https://lis.virginia.gov/cgi-bin/legp604.exe"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
BILL_NUM = "HB1"

st.set_page_config(page_title="v2500 Legacy ID Heist", page_icon="🗝️", layout="wide")
st.title("🗝️ v2500: The 'Legacy ID' Heist")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def run_heist():
    st.subheader("Step 1: Fetching 2026 Session Metadata...")
    
    # 1. Get All Sessions
    url = f"{API_BASE}/Session/api/GetSessionListAsync"
    try:
        r = session.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            all_sessions = []
            if isinstance(data, dict): all_sessions = data.get("Sessions", [])
            elif isinstance(data, list): all_sessions = data
            
            # 2. Find 2026
            target = next((s for s in all_sessions if s.get("SessionYear") == 2026), None)
            
            if target:
                st.success("✅ Found 2026 Session Object!")
                st.json(target)
                
                # 3. EXTRACT KEYS
                modern_code = target.get("SessionCode")
                legacy_id = target.get("LegacySessionID")
                session_id = target.get("SessionID")
                
                st.info(f"🔑 **Candidate Keys:** Modern=`{modern_code}` | LegacyID=`{legacy_id}` | ID=`{session_id}`")
                
                # 4. TEST THEM AGAINST THE WEBSITE
                st.divider()
                st.subheader("Step 2: Brute-Forcing the Website URL...")
                
                # We test variations of these keys
                candidates = [
                    str(modern_code),       # "20261"
                    str(modern_code)[2:],   # "261"
                    str(legacy_id),         # Whatever the API says
                    str(session_id),        # "59"
                    "261"                   # Explicit fallback
                ]
                # Remove duplicates
                candidates = list(set(candidates))
                
                for code in candidates:
                    if not code or code == "None": continue
                    
                    test_url = f"{CGI_BASE}?{code}+sum+{BILL_NUM}"
                    st.write(f"🔫 Testing: `{test_url}`")
                    
                    try:
                        h = {'User-Agent': 'Mozilla/5.0'}
                        r_web = session.get(test_url, headers=h, timeout=3)
                        
                        if "Sorry, the document" not in r_web.text:
                            st.success(f"🎉 **JACKPOT!** The correct website code is `{code}`!")
                            # Print snippet to prove it
                            if "Committee" in r_web.text:
                                st.info("Found 'Committee' in text!")
                            elif "Patron" in r_web.text:
                                st.info("Found 'Patron' (Valid Bill Page)")
                            return
                        else:
                            st.caption("❌ Failed (Document not found)")
                    except:
                        pass
                        
                st.error("❌ All candidate codes failed. The website might use a completely different mapping.")
                
            else:
                st.error("❌ Could not find 2026 session in API list.")
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Heist"):
    run_heist()
