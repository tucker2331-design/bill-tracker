import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v135 Final Map", page_icon="🗺️", layout="wide")
st.title("🗺️ v135: The Final Map (Hardcoded Success)")

# --- THE MASTER MAP (Derived from your JSON) ---
COMMITTEE_MAP = {
    "Privileges and Elections": "18",
    "P&E - Campaigns and Candidates": "106",
    "P&E - Voting Rights": "78",
    "P&E - Election Administration": "48",
    "P&E - Gubernatorial Appointments": "132",
    "Finance": "10",
    "Finance - Sub #1": "43",
    "Finance - Sub #2": "73",
    "Finance - Sub #3": "101",
    "Education": "9",
    "Education - K-12": "42",
    "Education - Higher Ed": "73",
    "Education - Early Childhood": "100",
    "Courts of Justice": "8",
    "Courts - Criminal": "41",
    "Courts - Civil": "71",
    "General Laws": "11",
    "General Laws - ABC/Gaming": "102",
    "General Laws - Housing": "74",
    "Health & Human Services": "197",
    "HHS - Health": "198",
    "HHS - Health Professions": "199",
    "HHS - Behavioral Health": "200",
    "HHS - Social Services": "201",
    "Transportation": "19",
    "Transportation - DMV": "51",
    "Transportation - Infrastructure": "79",
    "Public Safety": "15",
    "Public Safety - Firearms": "47",
    "Appropriations": "2",
    "Agriculture, Chesapeake": "1",
    "Counties, Cities, Towns": "7",
    "Labor and Commerce": "14",
    "Communications & Tech": "21",
    "Rules": "20"
}

# --- HELPER FUNCTIONS ---
def get_lis_link(cid):
    return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{cid}/committee-details"

# --- UI ---
st.sidebar.header("🚀 Quick Launch")

selected = st.sidebar.selectbox("Select Committee:", list(COMMITTEE_MAP.keys()))
cid = COMMITTEE_MAP[selected]
link = get_lis_link(cid)

st.sidebar.markdown(f"**Target ID:** `{cid}`")
st.sidebar.link_button(f"🔗 Go to {selected}", link)

# --- MAIN DISPLAY ---
st.header(f"🏛️ {selected}")
st.markdown(f"**Official LIS Link:** [{link}]({link})")

# Verify connection
try:
    r = requests.get(link, timeout=5)
    if r.status_code == 200:
        st.success("✅ Link is Valid and Active")
        
        # Determine likely chamber code for display
        chamber = "H" if int(cid) < 202 else "S" # Rough heuristic from your data
        
        # Use the "Ghost ID" API to fetch bills if possible
        api_url = "https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync"
        api_params = {"sessionCode": SESSION_CODE, "id": cid}
        # Note: We can't use the API without the Key/Cookies we found, 
        # so for now we just provide the perfect link for the user to click.
        
    else:
        st.warning(f"⚠️ Link returned status {r.status_code}")
except Exception as e:
    st.error(f"Connection Error: {e}")

st.divider()
st.markdown("""
### 🎯 How we fixed it:
1.  We found the **Hidden API** (`getCommitteesAsync`).
2.  We found the **Master Key** (`Webapikey`).
3.  We downloaded the **Full Directory** (User Provided).
4.  We mapped the "Ghost IDs" (e.g., `106` for Campaigns) to the names.

Now, instead of scraping empty pages, we generate the **exact integer link** the database expects.
""")
