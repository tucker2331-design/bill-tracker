import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
LIS_SESSION_ID = "261"

st.set_page_config(page_title="v108 Precision Reader", page_icon="🎯", layout="wide")
st.title("🎯 v108: The 'Precision' Reader (SFAC Fix)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 1. PRECISE SFAC SCRAPER ---
def scrape_sfac_site(url, target_date_obj, target_name):
    """
    Scrapes sfac.virginia.gov.
    CRITICAL CHANGE: Checks the 'Meeting' column to distinguish Full Committee from Subcommittees.
    """
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Format date (e.g., "January 27, 2026")
        target_date_str = target_date_obj.strftime("%B %-d, %Y")
        if "%-" in target_date_str: target_date_str = target_date_obj.strftime("%B %d, %Y").replace(" 0", " ")

        # Iterate ALL rows to find the specific match
        # Table structure: [Meeting Name] [Date] [Time] [Materials]
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            meeting_name = cols[0].get_text(" ", strip=True).lower()
            meeting_date = cols[1].get_text(" ", strip=True)
            
            # 1. Date Match
            if target_date_str not in meeting_date: continue
            
            # 2. Name Match (The Fix)
            # If API says "Senate Finance and Appropriations", we want the row that says "Senate Finance & Appropriations Committee"
            # We avoid rows that say "Subcommittee" unless the API asked for one.
            api_is_sub = "subcommittee" in target_name.lower()
            row_is_sub = "subcommittee" in meeting_name
            
            # Skip if mismatch (e.g. API wants Full, Row is Sub)
            if api_is_sub != row_is_sub: continue
            
            # If we are here, we have the RIGHT row.
            
            # 3. Extract Time
            raw_time = cols[2].get_text(" ", strip=True)
            # Handle "Time Change: 9:30 a.m."
            time_clean = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', raw_time)
            final_time = time_clean.group(1).upper() if time_clean else raw_time
            
            # 4. Extract Agenda Link
            agenda_link = None
            for a in cols[3].find_all('a', href=True):
                if "agenda" in a.get_text().lower():
                    agenda_link = a['href']
                    if not agenda_link.startswith("http"):
                        agenda_link = f"https://sfac.virginia.gov{agenda_link}"
                    break
            
            return {
                "Time": final_time,
                "Link": agenda_link,
                "Source": "SFAC Site (Precise Match)"
            }

    except: pass
    return None

# --- 2. BILL SCRAPER (Deep Diver) ---
def get_bills_deep_dive(url):
    if not url: return []
    if "granicus" in url: return [] 
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Scrape Function
        def scrape_soup(s):
            text = s.get_text(" ", strip=True)
            matches = re.findall(r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b', text, re.IGNORECASE)
            bills = set()
            for p, n in matches:
                bills.add(f"{p.upper().replace('.','').strip()}{n}")
            def sk(b):
                m = re.match(r"([A-Z]+)(\d+)", b)
                return (m.group(1), int(m.group(2))) if m else (b, 0)
            return sorted(list(bills), key=sk)

        # Attempt 1
        bills = scrape_soup(soup)
        if bills: return bills
        
        # Attempt 2 (Dive)
        target = None
        for a in soup.find_all('a', href=True):
            txt = a.get_text().lower()
            if "agenda" in txt or "docket" in txt or "meeting info" in txt:
                target = a['href']
                if target.startswith("/"):
                    base = "https://house.vga.virginia.gov" if "house.vga" in url else "https://lis.virginia.gov"
                    target = f"{base}{target}"
                break
        
        if target:
            resp2 = session.get(target, headers=HEADERS, timeout=5)
            return scrape_soup(BeautifulSoup(resp2.text, 'html.parser'))
            
        return []
    except: return []

# --- 3. HARDCODED MAP ---
COMMITTEE_MAP = {
    # HOUSE
    "appropriations": "H02", "finance": "H09", "courts": "H08",
    "commerce": "H11", "labor": "H11", "energy": "H11",
    "education": "H07", "health": "H13", "public safety": "H18",
    "transportation": "H15", "general laws": "H10",
    "counties": "H17", "rules": "H19", "agriculture": "H14",
    "communications": "H16", "privileges": "H01",
    # SENATE
    "agriculture": "S01", "education": "S02", "commerce": "S03",
    "courts": "S04", "finance": "S05", "general laws": "S06",
    "local gov": "S07", "privileges": "S08", "rehab": "S09",
    "transportation": "S10", "rules": "S11"
}

def construct_backup_link(owner_name):
    if not owner_name: return None
    name = owner_name.lower()
    cid = None
    for k, v in COMMITTEE_MAP.items():
        if k in name:
            cid = v
            if "senate" in name and cid.startswith("S"): break
            if "house" in name and cid.startswith("H"): break
    if not cid: return None
    if cid.startswith("H"): return f"https://house.vga.virginia.gov/committees/{cid}"
    return f"https://lis.virginia.gov/cgi-bin/legp604.exe?{LIS_SESSION_ID}+com+{cid}"

# --- 4. DATA FETCH ---
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

def extract_api_link(desc_text):
    if not desc_text: return None
    match = re.search(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    return match.group(1) if match else None

def parse_time_rank(time_str):
    if not time_str or "TBA" in str(time_str): return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- MAIN LOGIC ---

with st.spinner("Syncing..."):
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
    
    # 1. TIME HANDLING (Robust)
    raw_time = m.get("ScheduleTime")
    if not raw_time or not str(raw_time).strip():
        m['DisplayTime'] = "Time TBA" # Fallback for empty API strings
    else:
        m['DisplayTime'] = raw_time
        
    if m.get("IsCancelled") is True: 
        m['DisplayTime'] = "CANCELLED"
    
    # 2. LINK HANDLING
    api_link = extract_api_link(m.get("Description"))
    
    # SFAC Handler
    if api_link and "sfac.virginia.gov" in api_link:
        sfac = scrape_sfac_site(api_link, d, m.get("OwnerName", ""))
        if sfac:
            m['DisplayTime'] = sfac['Time'] # Overwrite with site time
            if sfac['Link']: api_link = sfac['Link']
            if "CANCEL" in sfac['Time'].upper(): m['DisplayTime'] = "CANCELLED"
            
    backup_link = construct_backup_link(m.get("OwnerName"))
    final_link = api_link if api_link else backup_link
    
    m['Link'] = final_link
    if final_link: links_to_scan.append(final_link)
    
    processed_events.append(m)

# Bill Scanning
bill_cache = {}
if links_to_scan:
    unique = list(set(links_to_scan))
    with st.spinner(f"Scanning {len(unique)} Dockets..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            fut = {executor.submit(get_bills_deep_dive, u): u for u in unique}
            for f in concurrent.futures.as_completed(fut):
                try: bill_cache[fut[f]] = f.result()
                except: bill_cache[fut[f]] = []

# Render
display_map = {}
for m in processed_events:
    d = m['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

if not display_map:
    st.info("No upcoming events.")
else:
    dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(dates))
    
    for i, dv in enumerate(dates):
        with cols[i]:
            st.markdown(f"### {dv.strftime('%a')}")
            st.caption(dv.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[dv]
            day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            for e in day_events:
                name = e.get("OwnerName", "Unknown").replace("Committee", "").replace("Virginia", "").strip()
                time_s = e.get("DisplayTime")
                link = e.get("Link")
                bills = bill_cache.get(link, [])
                
                is_cancelled = "CANCEL" in str(time_s).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        if "TBA" in str(time_s): st.warning(f"⚠️ {time_s}")
                        else: st.markdown(f"**⏰ {time_s}**")
                        
                        st.markdown(f"**{name}**")
                        
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("List"):
                                st.write(", ".join(bills))
                                if link: st.link_button("View Docket", link)
                        elif link:
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
