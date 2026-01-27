import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" # API uses this
LIS_URL_SESSION = "261" # LIS URLs use this (261 = 2026 Regular)

st.set_page_config(page_title="v105 Hardcoded Router", page_icon="🗺️", layout="wide")
st.title("🗺️ v105: The 'Hardcoded Truth' Router")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- THE ROSETTA STONE (Manual ID Mapping) ---
# Maps partial committee names to their PERMANENT LIS IDs
# Sources: LIS Website & House Clerk's Office
COMMITTEE_MAP = {
    # --- SENATE (Sxx) ---
    "agriculture": "S01",
    "commerce": "S03",
    "courts": "S04",
    "education": "S02", # Education & Health
    "finance": "S05", # Finance & Appropriations
    "general laws": "S06",
    "local gov": "S07",
    "privileges": "S08",
    "rehabilitation": "S09",
    "transportation": "S10",
    "rules": "S11",
    
    # --- HOUSE (Hxx) ---
    "privileges": "H01",
    "appropriations": "H02",
    "education": "H07",
    "courts": "H08",
    "finance": "H09",
    "general laws": "H10",
    "labor": "H11", # Labor & Commerce
    "commerce": "H11", # Commerce & Energy
    "health": "H13",
    "agriculture": "H14", # Ag / Chesapeake
    "transportation": "H15",
    "communications": "H16",
    "counties": "H17",
    "public safety": "H18",
    "rules": "H19",
}

def construct_lis_link(owner_name):
    """
    Takes a name like 'Senate Commerce and Labor' and builds the trusted LIS URL.
    """
    if not owner_name: return None, "None"
    
    name_lower = owner_name.lower()
    is_senate = "senate" in name_lower
    is_house = "house" in name_lower
    
    # Find the ID
    committee_id = None
    for key, cid in COMMITTEE_MAP.items():
        if key in name_lower:
            committee_id = cid
            # If we found a match, check chamber alignment to be safe
            if is_senate and cid.startswith("S"): break
            if is_house and cid.startswith("H"): break
            
    if not committee_id:
        return None, "No ID Match"
        
    # Construct the URL
    if committee_id.startswith("S"):
        # Senate Pattern: lis.virginia.gov/cgi-bin/legp604.exe?261+com+S03
        return f"https://lis.virginia.gov/cgi-bin/legp604.exe?{LIS_URL_SESSION}+com+{committee_id}", "Constructed (Senate)"
    
    if committee_id.startswith("H"):
        # House Pattern: house.vga.virginia.gov/committees/H02
        return f"https://house.vga.virginia.gov/committees/{committee_id}", "Constructed (House)"
        
    return None, "Unknown Chamber"

# --- HELPER FUNCTIONS ---
def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    if "TBA" in t_upper: return 9999
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

def get_bills_from_url(url):
    """
    Scrapes bills. Now running on TRUSTED URLs.
    """
    if not url: return []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        pattern = r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        bills = set()
        for p, n in matches:
            prefix = p.upper().replace(".", "").strip()
            bills.add(f"{prefix}{n}")
            
        def sort_key(b):
            match = re.match(r"([A-Z]+)(\d+)", b)
            if match: return match.group(1), int(match.group(2))
            return b, 0
        return sorted(list(bills), key=sort_key)
    except: return []

# --- 1. GET SCHEDULE ---
@st.cache_data(ttl=600)
def fetch_api_schedule():
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

with st.spinner("Building Schedule..."):
    raw_events = fetch_api_schedule()

today = datetime.now().date()
processed_events = []
links_to_scan = []

for m in raw_events:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    m['DateObj'] = d
    m['DisplayTime'] = m.get("ScheduleTime", "TBA")
    
    # Check Cancellation (API Field)
    if m.get("IsCancelled") is True:
        m['DisplayTime'] = "CANCELLED"
    
    # --- THE ROUTER ---
    # Ignore the API link. Build our own.
    constructed_link, link_source = construct_lis_link(m.get("OwnerName"))
    
    m['Link'] = constructed_link
    m['LinkSource'] = link_source
    
    if m['Link']:
        links_to_scan.append(m['Link'])
        
    processed_events.append(m)

# Scan Bills (on the Trusted Links)
bill_cache = {}
if links_to_scan:
    unique_links = list(set(links_to_scan))
    with st.spinner(f"Scanning {len(unique_links)} Trusted Dockets..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(get_bills_from_url, url): url for url in unique_links}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try: bill_cache[url] = future.result()
                except: bill_cache[url] = []

# Display
display_map = {}
for m in processed_events:
    d = m['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

if not display_map:
    st.info("No upcoming events found.")
else:
    sorted_dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            for event in day_events:
                name = event.get("OwnerName", "Unknown")
                clean_name = name.replace("Committee", "").replace("Virginia", "").strip()
                time_disp = event.get("DisplayTime")
                link = event.get("Link")
                source = event.get("LinkSource")
                bills = bill_cache.get(link, [])
                
                is_cancelled = "CANCEL" in str(time_disp).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{clean_name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        # Time
                        if "TBA" in str(time_disp) or "Not Listed" in str(time_disp):
                            st.warning(f"⚠️ {time_disp}")
                        else:
                            st.markdown(f"**⏰ {time_disp}**")
                        
                        st.markdown(f"**{clean_name}**")
                        
                        # Bills
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View List"):
                                st.write(", ".join(bills))
                                if link: st.link_button("View Docket", link)
                        elif link:
                            # If it's a subcommittee, warn them
                            btn_label = "View Parent Docket" if "Subcommittee" in name else "View Docket"
                            st.link_button(btn_label, link)
                        else:
                            st.caption("*(No ID Match)*")
                            
                        # Debug info to prove we swapped it
                        # st.caption(f"Src: {source}")
