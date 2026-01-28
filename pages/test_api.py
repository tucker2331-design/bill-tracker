import streamlit as st
import requests

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
COMMITTEE_ID = "18" 
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v303 Kitchen Sink", page_icon="🚰", layout="wide")
st.title("🚰 v303: The Kitchen Sink Scanner")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Webapikey': WEB_API_KEY
}

# 50 Common Variations to try
COMMON_ACTIONS = [
    "GetLegislationListAsync", "GetLegislationList", "GetLegislation", "GetBills", "GetBillsList",
    "GetCommitteeLegislation", "GetCommitteeLegislationList", "GetCommitteeBills",
    "GetDocket", "GetDocketList", "GetAgenda", "GetAgendaList",
    "GetLegislationByCommittee", "GetBillsByCommittee",
    "GetReferrals", "GetReferralList", "GetReferredLegislation",
    "GetDocuments", "GetDocumentList", "GetFiles",
    "GetSchedule", "GetMeetingLegislation"
]

def fire_sink():
    # We focus on the Service we know exists: CommitteeLegislation
    service = "CommitteeLegislation"
    
    st.write(f"### 🎯 Targeting Service: `{service}`")
    
    progress_bar = st.progress(0)
    
    found_any = False
    
    for i, action in enumerate(COMMON_ACTIONS):
        # Update Progress
        progress_bar.progress((i + 1) / len(COMMON_ACTIONS))
        
        # Construct URL
        url = f"{BASE_URL}/{service}/api/{action}"
        
        try:
            # Try both GET and POST just in case
            resp = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "committeeId": COMMITTEE_ID}, timeout=1)
            
            if resp.status_code == 200:
                # Check content type
                if "application/json" in resp.headers.get("Content-Type", ""):
                    st.success(f"✅ **JACKPOT!** `{action}` returned JSON!")
                    st.json(resp.json())
                    found_any = True
                    break # Stop if we find it
                elif len(resp.text) < 500 and "Error" not in resp.text:
                    st.info(f"⚠️ `{action}` returned 200 OK (Text): {resp.text}")
            
        except:
            pass
            
    if not found_any:
        st.error("❌ Scanned 50 endpoints. No direct hits on JSON data.")

if st.button("🔴 Fire the Kitchen Sink"):
    fire_sink()
