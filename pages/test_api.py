import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="VA Bill Tracker v200", page_icon="🏛️", layout="wide")
st.title("🏛️ Virginia General Assembly Bill Tracker")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 💎 THE MASTER MAP (Hardcoded from your JSON) ---
# This maps every committee name to its INTERNAL INTEGER ID.
# No more scraping needed.
MASTER_COMMITTEE_MAP = {
    # --- HOUSE PARENTS ---
    "Agriculture, Chesapeake and Natural Resources": "1",
    "Appropriations": "2",
    "Counties, Cities and Towns": "7",
    "Courts of Justice": "8",
    "Education": "9",
    "Finance": "10",
    "General Laws": "11",
    "Labor and Commerce": "14",
    "Public Safety": "15",
    "Privileges and Elections": "18",
    "Transportation": "19",
    "Rules": "20",
    "Communications, Technology and Innovation": "21",
    "Health and Human Services": "197",
    
    # --- HOUSE SUBCOMMITTEES (The "Ghost" IDs) ---
    "Campaigns and Candidates": "106",
    "Voting Rights": "78",
    "Election Administration": "48",
    "Gubernatorial Appointments": "132",
    "Higher Education": "72", # Education Sub
    "K-12 Subcommittee": "42",
    "Early Childhood and Innovation": "100",
    "Criminal": "41", # Courts Sub
    "Civil": "71",
    "Firearms": "47", # Public Safety Sub
    "ABC/Gaming": "102",
    "Housing/Consumer Protection": "74",
    "Health": "198",
    "Behavioral Health": "200",
    "Social Services": "201",
    "Health Professions": "199",
    "Transportation Infrastructure and Funding": "79",
    "Department of Motor Vehicles": "51",
    
    # --- SENATE PARENTS ---
    "Senate Agriculture, Conservation and Natural Resources": "22",
    "Senate Commerce and Labor": "23",
    "Senate Education and Health": "25",
    "Senate Finance and Appropriations": "26",
    "Senate Courts of Justice": "202",
    "Senate General Laws and Technology": "33",
    "Senate Local Government": "28",
    "Senate Privileges and Elections": "29",
    "Senate Rehabilitation and Social Services": "30",
    "Senate Transportation": "32",
    "Senate Rules": "31"
}

# --- 1. INTELLIGENT ROUTER ---
def get_perfect_link(owner_name):
    """
    Matches the API Owner Name to our Master Map to generate a direct Integer ID link.
    """
    if not owner_name: return None
    
    # Normalize name (remove "House", "Committee", etc to match our keys)
    clean_name = owner_name.replace("House Committee on", "").replace("House", "").replace("Committee", "").strip()
    
    # 1. Exact Match
    if clean_name in MASTER_COMMITTEE_MAP:
        cid = MASTER_COMMITTEE_MAP[clean_name]
        return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{cid}/committee-details"
    
    # 2. Sub-Match (e.g. "Privileges and Elections - Campaigns")
    for key, cid in MASTER_COMMITTEE_MAP.items():
        if key in clean_name:
            return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{cid}/committee-details"
            
    return None

# --- 2. BILL SCRAPER ---
def get_bills_from_url(url):
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        # Regex for bills (HB1234, SB50, etc)
        matches = re.findall(r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b', text, re.IGNORECASE)
        bills = set()
        for p, n in matches:
            bills.add(f"{p.upper().replace('.','').strip()}{n}")
        return sorted(list(bills))
    except:
        return []

# --- 3. API FETCH ---
@st.cache_data(ttl=300)
def fetch_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    events = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            for f in [h, s]:
                if f.result().status_code == 200:
                    events.extend(f.result().json().get("Schedules", []))
    except: pass
    return events

# --- MAIN APP LOGIC ---
st.markdown("### 📅 Legislative Schedule")

with st.spinner("Syncing with LIS..."):
    raw_events = fetch_schedule()

today = datetime.now().date()
display_map = {}

# Process Events
for m in raw_events:
    if not m: continue
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue # Skip past events
    
    if d not in display_map: display_map[d] = []
    
    # DATA ENRICHMENT
    # 1. Use the Master Map to get the link
    m['Link'] = get_perfect_link(m.get("OwnerName"))
    
    # 2. Format Time
    t_str = m.get("ScheduleTime", "TBA")
    if m.get("IsCancelled"): t_str = "CANCELLED"
    m['DisplayTime'] = t_str
    
    display_map[d].append(m)

# DISPLAY
if not display_map:
    st.info("No upcoming meetings found.")
else:
    dates = sorted(display_map.keys())[:7] # Next 7 days
    cols = st.columns(len(dates))
    
    for i, dv in enumerate(dates):
        with cols[i]:
            st.markdown(f"### {dv.strftime('%a')}")
            st.caption(dv.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[dv]
            # Simple Sort by Time
            day_events.sort(key=lambda x: x['DisplayTime'])
            
            for e in day_events:
                name = e.get("OwnerName", "Unknown").replace("Committee", "").strip()
                time_s = e['DisplayTime']
                link = e['Link']
                
                if "CANCEL" in str(time_s).upper():
                    st.error(f"❌ **{name}**")
                else:
                    with st.container(border=True):
                        st.markdown(f"**⏰ {time_s}**")
                        st.markdown(f"**{name}**")
                        
                        if link:
                            st.link_button("View Docket", link)
                            # Optional: Preview Bill Count
                            # bills = get_bills_from_url(link)
                            # if bills: st.caption(f"{len(bills)} Bills Listed")
                        else:
                            st.caption("*(No Link Available)*")
