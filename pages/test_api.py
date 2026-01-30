import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# CONTROL GROUP (2025 Regular Session - Known Data)
TEST_SESSION = "20251" 
TEST_COMMITTEE = 1 # Agriculture

st.set_page_config(page_title="v2000 Handshake Protocol", page_icon="🤝", layout="wide")
st.title("🤝 v2000: The 'Handshake' Protocol")

# 1. INITIALIZE SESSION WITH BROWSER HEADERS
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'WebAPIKey': API_KEY, # Keep our key
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
})

def run_handshake():
    st.subheader("Step 1: Establishing Session State (The Handshake)...")
    
    # A. Hit the Home Page
    try:
        r1 = session.get("https://lis.virginia.gov/")
        st.write(f"🏠 Home Page: Status {r1.status_code}")
    except:
        st.warning("Failed to hit home page")

    # B. Hit a CGI Page (Forces ASP.NET Session generation)
    # This is the "Bills" menu page for 2026
    try:
        r2 = session.get("https://lis.virginia.gov/cgi-bin/legp604.exe?261+men+BIL")
        st.write(f"📜 CGI Portal: Status {r2.status_code}")
    except:
        st.warning("Failed to hit CGI portal")
        
    # C. CHECK COOKIES
    cookies = session.cookies.get_dict()
    if cookies:
        st.success("✅ Cookies Acquired!")
        st.json(cookies)
    else:
        st.warning("⚠️ No cookies received. Server might be stateless (unlikely).")

    # --- STEP 2: RETRY THE SEARCH (WITH COOKIES) ---
    st.divider()
    st.subheader(f"Step 2: Retrying 2025 Search (Session {TEST_SESSION})...")
    
    search_url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
    
    payload = {
        "SessionCode": TEST_SESSION,
        "CommitteeId": TEST_COMMITTEE,
        "ChamberCode": "H"
    }
    
    try:
        # We perform the same POST request as v1900, but now we have cookies
        r = session.post(search_url, json=payload, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            
            # Unwrap
            bills = []
            if isinstance(data, dict):
                 if "Legislation" in data: bills = data["Legislation"]
                 elif "Items" in data: bills = data["Items"]
                 elif "Results" in data: bills = data["Results"]
            elif isinstance(data, list):
                bills = data
            
            if bills:
                st.success(f"🎉 **HANDSHAKE SUCCESS!** Found {len(bills)} bills!")
                st.dataframe(bills[:5])
                st.balloons()
            else:
                st.warning("⚠️ 200 OK (Empty List) - Cookies didn't fix it.")
                st.write("Response:", data)
                
        elif r.status_code == 204:
            st.error("❌ Still 204 No Content.")
        else:
            st.error(f"❌ Failed: {r.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Handshake"):
    run_handshake()
