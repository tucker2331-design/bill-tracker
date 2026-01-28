import streamlit as st
import requests

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
COMMITTEE_ID = "18" # Internal ID for Privileges & Elections
COMMITTEE_CODE = "H18"
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v302 Doc Hunter", page_icon="📜", layout="wide")
st.title("📜 v302: The Documentation Hunter")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Webapikey': WEB_API_KEY
}

def probe(service_name, endpoint_name, params):
    # Construct URL: https://lis.virginia.gov/CommitteeLegislation/api/GetLegislationListAsync
    url = f"{BASE_URL}/{service_name}/api/{endpoint_name}"
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"Testing `{service_name}` -> `{endpoint_name}`...")
    
    try:
        resp = session.get(url, headers=HEADERS, params=params, timeout=3)
        with col2:
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if data:
                        st.success("✅ HIT!")
                        return data
                    else:
                        st.warning("⚠️ Empty")
                except:
                    st.error("❌ Not JSON")
            elif resp.status_code == 404:
                st.caption("❌ 404 (Missing)")
            else:
                st.error(f"❌ {resp.status_code}")
    except Exception as e:
        with col2:
            st.error("Error")
    return None

if st.button("🔴 Test Service Endpoints"):
    
    st.subheader("1. Service: CommitteeLegislation")
    st.info("Hypothesis: This service links Committees to Bills (aka Dockets).")
    
    # Try getting legislation by Committee ID
    hit = probe("CommitteeLegislation", "GetLegislationListAsync", 
                {"sessionCode": SESSION_CODE, "committeeId": COMMITTEE_ID})
    if hit: st.json(hit)
        
    hit = probe("CommitteeLegislation", "GetCommitteeLegislationListAsync", 
                {"sessionCode": SESSION_CODE, "committeeId": COMMITTEE_ID})
    if hit: st.json(hit)

    st.divider()
    
    st.subheader("2. Service: Legislation")
    st.info("Hypothesis: Maybe we ask for bills and filter by committee?")
    
    hit = probe("Legislation", "GetLegislationByCommitteeAsync", 
                {"sessionCode": SESSION_CODE, "committeeId": COMMITTEE_ID})
    if hit: st.json(hit)

    st.divider()

    st.subheader("3. Service: LegislationCollections")
    st.info("Hypothesis: Dockets are 'Collections' of bills.")
    
    hit = probe("LegislationCollections", "GetDocketListAsync", 
                {"sessionCode": SESSION_CODE, "committeeId": COMMITTEE_ID})
    if hit: st.json(hit)
