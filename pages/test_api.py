import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="VA Bill Tracker v201", page_icon="🏛️", layout="wide")
st.title("🏛️ Virginia General Assembly Bill Tracker")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 💎 THE CORRECTED MASTER MAP (Using CODES, not IDs) ---
# We use the "CommitteeNumber" from the JSON (e.g., H18003) because that is what the WEBSITE needs.
MASTER_COMMITTEE_MAP = {
    # --- HOUSE PARENTS ---
    "Agriculture, Chesapeake and Natural Resources": "H01",
    "Appropriations": "H02",
    "Counties, Cities and Towns": "H07",
    "Courts of Justice": "H08",
    "Education": "H09",
    "Finance": "H10",
    "General Laws": "H11",
    "Labor and Commerce": "H14",
    "Public Safety": "H15",
    "Privileges and Elections": "H18",
    "Transportation": "H19",
    "Rules": "H20",
    "Communications, Technology and Innovation": "H21",
    "Health and Human Services": "H24",
    
    # --- HOUSE SUBCOMMITTEES (The "Ghost" Codes) ---
    "Campaigns and Candidates": "H18003",
    "Voting Rights": "H18002",
    "Election Administration": "H18001",
    "Gubernatorial Appointments": "H18004",
    "Higher Education": "H09002",
    "K-12 Subcommittee": "H09001",
    "Early Childhood and Innovation": "H09003",
    "Criminal": "H08001",
    "Civil": "H08002",
    "Firearms": "H15001",
    "ABC/Gaming": "H11003",
    "Housing/Consumer Protection": "H11002",
    "Health": "H24001",
    "Behavioral Health": "H24003",
    "Social Services": "H24004",
    "Health Professions": "H24002",
    "Transportation Infrastructure and Funding": "H19002",
    "Department of Motor Vehicles": "H19001",
    
    # --- FINANCE SUBS ---
    "Subcommittee #1": "H10001",
    "Subcommittee #2": "H10002",
    "Subcommittee #3": "H10003",

    # --- SENATE PARENTS ---
    "Senate Agriculture, Conservation and Natural Resources": "S01",
    "Senate Commerce and Labor": "S02",
    "Senate Education and Health": "S04",
    "Senate Finance and Appropriations": "S05",
    "Senate Courts of Justice": "S13", # Note: Senate Courts is S13
    "Senate General Laws and Technology": "S12",
    "Senate Local Government": "S07",
    "Senate Privileges and Elections": "S08",
    "Senate Rehabilitation and Social Services": "S09",
    "Senate Transportation": "S11",
    "Senate Rules": "S10"
}

# --- 1. INTELLIGENT ROUTER ---
def get_perfect_link(owner_name):
    """
    Matches the API Owner Name to our Master Map (Codes) to generate a working LIS link.
    """
    if not owner_name: return None
    
    # Normalize name
    clean_name = owner_name.replace("House Committee on", "").replace("House", "").replace("Committee", "").strip()
    
    # 1. Exact Match
    if clean_name in MASTER_COMMITTEE_MAP:
        code = MASTER_COMMITTEE_MAP[clean_name]
        return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{code}/committee-details"
    
    # 2. Sub-Match
    for key, code in MASTER_COMMITTEE_MAP.items():
        if key in clean_name:
            return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{code}/committee-details"
            
    return None

# --- 2. BILL SCRAPER (Now that links work, this will work) ---
def get_bills_from_url(url):
    try:
        resp = session.get(url, headers=HEADERS, timeout=3)
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
    if d < today: continue 
    
    if d not in display_map: display_map[d] = []
    
    # LINK GEN
    m['Link'] = get_perfect_link(m.get("OwnerName"))
    
    # TIME FORMATTING (Safe)
    t_str = m.get("ScheduleTime")
    if m.get("IsCancelled"): 
        m['DisplayTime'] = "CANCELLED"
    elif t_str:
        m['DisplayTime'] = t_str
    else:
        m['DisplayTime'] = "Time TBA"
    
    display_map[d].append(m)

# DISPLAY
if not display_map:
    st.info("No upcoming meetings found.")
else:
    dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(dates))
    
    for i, dv in enumerate(dates):
        with cols[i]:
            st.markdown(f"### {dv.strftime('%a')}")
            st.caption(dv.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[dv]
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
                            # Now that link works, we can optionally scrape count
                            # (Commented out to keep it fast, uncomment if you want auto-counts)
                            # bills = get_bills_from_url(link)
                            # if bills: st.caption(f"{len(bills)} Bills Listed")
                            
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link Available)*")
