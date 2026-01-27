import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
LIS_SESSION_ID = "261" # 2026 Regular Session

st.set_page_config(page_title="v106 Deep Diver", page_icon="🤿", layout="wide")
st.title("🤿 v106: The 'Deep Diver' (Multi-Step Scraper)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 1. HARDCODED MAP (Backup for Missing Links) ---
COMMITTEE_MAP = {
    # HOUSE (Committees/Hxx)
    "appropriations": "H02", "finance": "H09", "courts": "H08",
    "commerce": "H11", "labor": "H11", "energy": "H11",
    "education": "H07", "health": "H13", "public safety": "H18",
    "transportation": "H15", "general laws": "H10",
    "counties": "H17", "rules": "H19", "agriculture": "H14",
    "communications": "H16", "privileges": "H01",
    
    # SENATE (com+Sxx)
    "agriculture": "S01", "education": "S02", "commerce": "S03",
    "courts": "S04", "finance": "S05", "general laws": "S06",
    "local gov": "S07", "privileges": "S08", "rehab": "S09",
    "transportation": "S10", "rules": "S11"
}

def construct_backup_link(owner_name):
    if not owner_name: return None
    name_lower = owner_name.lower()
    cid = None
    
    # Simple keyword match
    for key, id_val in COMMITTEE_MAP.items():
        if key in name_lower:
            cid = id_val
            # Ensure chamber match
            if "senate" in name_lower and cid.startswith("S"): break
            if "house" in name_lower and cid.startswith("H"): break
            
    if not cid: return None
    
    if cid.startswith("H"): return f"https://house.vga.virginia.gov/committees/{cid}"
    if cid.startswith("S"): return f"https://lis.virginia.gov/cgi-bin/legp604.exe?{LIS_SESSION_ID}+com+{cid}"
    return None

# --- 2. THE DEEP DIVER SCRAPER ---
def scrape_bills_from_page(soup):
    """Extracts bill numbers (HB100, SB50) from a Soup object."""
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

def get_bills_deep_dive(url):
    """
    Step 1: Scrape URL.
    Step 2: If 0 bills, look for 'Agenda'/'Docket' link.
    Step 3: Dive and scrape that.
    """
    if not url: return []
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # ATTEMPT 1: Direct Scrape
        bills = scrape_bills_from_page(soup)
        if bills: return bills # Found them!
        
        # ATTEMPT 2: The Dive
        # Look for links containing specific keywords
        target_link = None
        for a in soup.find_all('a', href=True):
            txt = a.get_text().lower()
            if "agenda" in txt or "docket" in txt or "meeting info" in txt:
                target_link = a['href']
                if target_link.startswith("/"):
                    # Handle relative URLs correctly based on domain
                    if "house.vga" in url: base = "https://house.vga.virginia.gov"
                    elif "lis.virginia" in url: base = "https://lis.virginia.gov"
                    else: base = "" # Hope it's absolute or we fail
                    target_link = f"{base}{target_link}"
                break # Take the first likely candidate
        
        if target_link:
            # DIVE!
            resp_2 = session.get(target_link, headers=HEADERS, timeout=5)
            soup_2 = BeautifulSoup(resp_2.text, 'html.parser')
            return scrape_bills_from_page(soup_2)
            
        return []
    except: return []

# --- 3. HELPER FUNCTIONS ---
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

def extract_api_link(desc_text):
    if not desc_text: return None
    match = re.search(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    if match: return match.group(1)
    return None

# --- 4. API FETCH ---
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

with st.spinner("Fetching API & Diving Dockets..."):
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
    if m.get("IsCancelled") is True: m['DisplayTime'] = "CANCELLED"
    
    # LINK STRATEGY
    # 1. Prefer API Link (Deepest)
    api_link = extract_api_link(m.get("Description"))
    # 2. Fallback to Constructed Link (Homepage)
    backup_link = construct_backup_link(m.get("OwnerName"))
    
    final_link = api_link if api_link else backup_link
    m['Link'] = final_link
    m['LinkSource'] = "API" if api_link else "Backup"
    
    if final_link:
        links_to_scan.append(final_link)
        
    processed_events.append(m)

# AUTO-SCAN BILLS
bill_cache = {}
if links_to_scan:
    unique_links = list(set(links_to_scan))
    with st.spinner(f"Deep Diving {len(unique_links)} Pages..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(get_bills_deep_dive, url): url for url in unique_links}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try: bill_cache[url] = future.result()
                except: bill_cache[url] = []

# DISPLAY
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
                bills = bill_cache.get(link, [])
                
                is_cancelled = "CANCEL" in str(time_disp).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{clean_name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        if "TBA" in str(time_disp) or "Not Listed" in str(time_disp):
                            st.warning(f"⚠️ {time_disp}")
                        else:
                            st.markdown(f"**⏰ {time_disp}**")
                        
                        st.markdown(f"**{clean_name}**")
                        
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View List"):
                                st.write(", ".join(bills))
                                if link: st.link_button("View Docket", link)
                        elif link:
                            # If no bills found, but we have a link
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
