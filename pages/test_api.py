import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="VA Bill Tracker v203", page_icon="🏛️", layout="wide")
st.title("🏛️ Virginia General Assembly Bill Tracker")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- MASTER MAP (Codes) ---
MASTER_COMMITTEE_MAP = {
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
    # HOUSE SUBS
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
    "Highway Safety and Policy": "H19004",
    "Subcommittee #1": "H10001",
    "Subcommittee #2": "H10002",
    "Subcommittee #3": "H10003",
    # SENATE
    "Senate Agriculture, Conservation and Natural Resources": "S01",
    "Senate Commerce and Labor": "S02",
    "Senate Education and Health": "S04",
    "Senate Finance and Appropriations": "S05",
    "Senate Courts of Justice": "S13",
    "Senate General Laws and Technology": "S12",
    "Senate Local Government": "S07",
    "Senate Privileges and Elections": "S08",
    "Senate Rehabilitation and Social Services": "S09",
    "Senate Transportation": "S11",
    "Senate Rules": "S10"
}

# --- 1. INTELLIGENT ROUTER ---
def get_committee_lobby_link(owner_name):
    if not owner_name: return None
    clean_name = owner_name.replace("House Committee on", "").replace("House", "").replace("Committee", "").strip()
    
    # Exact Match
    if clean_name in MASTER_COMMITTEE_MAP:
        code = MASTER_COMMITTEE_MAP[clean_name]
        return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{code}/committee-details"
    
    # Partial Match
    for key, code in MASTER_COMMITTEE_MAP.items():
        if key in clean_name:
            return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{code}/committee-details"
    return None

# --- 2. THE DOCKET HUNTER (V2 - Aggressive) ---
def find_docket_for_date(committee_url, meeting_date):
    """
    Scrapes the Lobby page. Tries to find the exact date row. 
    If failing that, grabs the first 'Docket' link available.
    """
    if not committee_url: return None, [], "No URL"
    
    try:
        resp = session.get(committee_url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Strategy 1: Find Exact Date (e.g. "January 29")
        # We assume the user wants the docket for the meeting date
        target_str = meeting_date.strftime("%B %d").replace(" 0", " ") # "January 29"
        
        # Find all links that say "Docket" or "Agenda"
        docket_links = soup.find_all('a', href=True, string=re.compile(r'(Docket|Agenda)', re.IGNORECASE))
        
        best_link = None
        match_type = "Fallback"
        
        # Check if any docket link is near our date
        for link in docket_links:
            # Look at the text surrounding this link (parent row or container)
            row_text = link.find_parent().find_parent().get_text() 
            if target_str in row_text:
                best_link = link['href']
                match_type = "Exact Date"
                break
        
        # Strategy 2: If no date match, grab the FIRST docket link (usually the upcoming one)
        if not best_link and docket_links:
            best_link = docket_links[0]['href']
            match_type = "First Available"
            
        if best_link:
            if not best_link.startswith("http"):
                best_link = f"https://lis.virginia.gov{best_link}"
            
            # Now scrape the bills from that docket
            bills = scrape_bills(best_link)
            return best_link, bills, match_type
            
        return committee_url, [], "Lobby Only"
        
    except Exception as e:
        return committee_url, [], f"Error: {str(e)}"

def scrape_bills(url):
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

# --- 3. SCHEDULE FETCH ---
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

# --- MAIN LOGIC ---
st.markdown("### 📅 Legislative Schedule")

with st.spinner("Hunting for Dockets..."):
    raw_events = fetch_schedule()

today = datetime.now().date()
final_events = []

# Filter & Prep
for m in raw_events:
    if not m: continue
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    m['DateObj'] = d
    m['LobbyLink'] = get_committee_lobby_link(m.get("OwnerName"))
    
    # Format Time
    t_str = m.get("ScheduleTime")
    if m.get("IsCancelled"): m['DisplayTime'] = "CANCELLED"
    elif t_str: m['DisplayTime'] = t_str
    else: m['DisplayTime'] = "Time TBA"
    
    final_events.append(m)

# --- CONCURRENT ENRICHMENT ---
def enrich_event(evt):
    if evt['LobbyLink'] and evt['DisplayTime'] != "CANCELLED":
        deep_link, bills, status = find_docket_for_date(evt['LobbyLink'], evt['DateObj'])
        evt['DeepLink'] = deep_link
        evt['Bills'] = bills
        evt['Status'] = status
    else:
        evt['DeepLink'] = evt.get('LobbyLink')
        evt['Bills'] = []
        evt['Status'] = "No Link"
    return evt

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    final_events = list(executor.map(enrich_event, final_events))

# --- DISPLAY ---
display_map = {}
for m in final_events:
    d = m['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

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
                link = e.get('DeepLink')
                bills = e.get('Bills', [])
                status = e.get('Status', '')
                
                if "CANCEL" in str(time_s).upper():
                    st.error(f"❌ **{name}**")
                else:
                    with st.container(border=True):
                        st.markdown(f"**⏰ {time_s}**")
                        st.markdown(f"**{name}**")
                        
                        # Debug Status (Tiny text)
                        if "Lobby" in status:
                            st.caption(f"⚠️ {status}")
                        else:
                            st.caption(f"✓ {status}")

                        if bills:
                            st.success(f"**{len(bills)} Bills Found**")
                            with st.expander("Show Bills"):
                                st.write(", ".join(bills))
                                if link: st.link_button("Go to Docket", link)
                        elif link:
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
