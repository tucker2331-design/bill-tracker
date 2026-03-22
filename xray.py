import streamlit as st
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time

st.set_page_config(page_title="Sandbox 4", layout="wide")
st.title("🛡️ Sandbox 4: Network Armor & DLQ")

# --- 1. The Network Armor ---
def get_armored_session():
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'})
    # Exponential backoff factor of 3 (Waits 3s, then 6s, then 12s if blocked)
    retries = Retry(total=3, backoff_factor=3, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# --- 2. DLQ Routing Logic ---
def route_vote(csv_committee_name, is_pdf_corrupt=False):
    LEXICON = {
        "House Committee on Transportation": ["transportation"],
        "Senate Committee on Finance and Appropriations": ["finance and appropriations", "finance"]
    }
    
    if is_pdf_corrupt: 
        return "⚠️ [Agenda unreadable - Manual check required]"

    outcome_lower = csv_committee_name.lower()
    for api_name, aliases in LEXICON.items():
        if any(alias in outcome_lower for alias in aliases): 
            return api_name
            
    return f"⚠️ [Unmapped] {csv_committee_name} (Ledger)"

# --- EXECUTE TESTS ---
st.header("Test A: Armored Network Request")
st.write("Targeting: `https://house.vga.virginia.gov`")
try:
    http = get_armored_session()
    start = time.time()
    res = http.get("https://house.vga.virginia.gov", timeout=5)
    duration = round(time.time() - start, 2)
    st.success(f"✅ Connection Successful! Status: {res.status_code}. Time taken: {duration} seconds.")
except Exception as e:
    st.error(f"❌ Failed gracefully (Timeout or Blocked): {e}")

st.header("Test B: Dead Letter Queue (DLQ) Routing")
st.info(f"**Scenario 1 (Perfect Lexicon Match):** 'Reported from Transportation'  \n➡️ `{route_vote('Reported from Transportation')}`")
st.warning(f"**Scenario 2 (Rogue Clerk Unmapped Name):** 'Reported from Ad-Hoc AI Sub'  \n➡️ `{route_vote('Reported from Ad-Hoc AI Sub')}`")
st.error(f"**Scenario 3 (Corrupt PDF Catch):** 'House Transportation'  \n➡️ `{route_vote('House Transportation', is_pdf_corrupt=True)}`")
