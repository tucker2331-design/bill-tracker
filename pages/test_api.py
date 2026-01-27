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

st.set_page_config(page_title="v107 Marketing Reader", page_icon="📰", layout="wide")
st.title("📰 v107: The 'Marketing' Reader (SFAC Fix)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 1. SPECIAL HANDLERS (The Fix for SFAC) ---
def scrape_sfac_site(url, target_date_obj):
    """
    Scrapes the sfac.virginia.gov table for specific dates.
    Returns: {time, link, note}
    """
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Format target date to match site (e.g., "January 26, 2026")
        target_str = target_date_obj.strftime("%B %-d, %Y") # Linux/Mac
        # Fallback for Windows strftime if needed
        if "%-" in target_str: target_str = target_date_obj.strftime("%B %d, %Y").replace(" 0", " ")

        # Find the table row with this date
        # Strategy: Search all 'td' for the date, then look at siblings
        date_cell = soup.find(string=re.compile(target_str))
        
        if date_cell:
            row = date_cell.find_parent('tr')
            cols = row.find_all('td')
            
            # Column mapping (approximate based on screenshot)
            # Col 0: Meeting Name, Col 1: Date, Col 2: Time, Col 3: Materials
            
            # 1. Grab Time
            raw_time = cols[2].get_text(" ", strip=True)
            # Clean "Time Change: 9:30 a.m." -> "9:30 AM"
            time_clean = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', raw_time)
            final_time = time_clean.group(1).upper() if time_clean else raw_time
            
            # 2. Grab Agenda Link
            agenda_link = None
            materials_col = cols[3]
            for a in materials_col.find_all('a', href=True):
                txt = a.get_text().lower()
                if "agenda" in txt:
                    agenda_link = a['href']
                    if not agenda_link.startswith("http"): 
                        agenda_link = f"https://sfac.virginia.gov{agenda_link}"
                    break
            
            return {
                "Time": final_time,
                "Link": agenda_link,
                "Source": "SFAC Site"
            }
            
    except: pass
    return None

# --- 2. BILL SCRAPER (Deep Diver) ---
def get_bills_deep_dive(url):
    if not url: return []
    if "granicus" in url: return [] # Skip video streams
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for bills
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

# --- 3. HARDCODED MAP (Backup) ---
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
    for key, id_val in COMMITTEE_MAP.items():
        if key in name_lower:
            cid = id_val
            if "senate" in name_lower and cid.startswith("S"): break
            if "house" in name_lower and cid.startswith("H"): break
    
    if not cid: return None
    if cid.startswith("H"): return f"https://house.vga.virginia.gov/committees/{cid}"
    if cid.startswith("S"): return f"https://lis.virginia.gov/cgi-bin/legp604.exe?{LIS_SESSION_ID}+com+{cid}"
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

# --- 5. EXTRACT API LINK ---
def extract_api_link(desc_text):
    if not desc_text: return None
    match = re.search(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    if match: return match.group(1)
    return None

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

# --- MAIN LOGIC ---

with st.spinner("Syncing..."):
    raw_events = fetch_api_schedule()

today = datetime.now().date()
processed_events = []
links_to_scan = []

# Process
for m in raw_events:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    m['DateObj'] = d
    m['DisplayTime'] = m.get("ScheduleTime", "TBA")
    if m.get("IsCancelled") is True: m['DisplayTime'] = "CANCELLED"
    
    # 1. LINK LOGIC
    api_link = extract_api_link(m.get("Description"))
    
    # SPECIAL HANDLER: SFAC
    # If the API link is the generic "sfac.virginia.gov", we must scrape it for the REAL info
    if api_link and "sfac.virginia.gov" in api_link:
        # Run the specialized scraper
        sfac_data = scrape_sfac_site(api_link, d)
        if sfac_data:
            # Override with fresh data
            m['DisplayTime'] = sfac_data['Time']
            if sfac_data['Link']: api_link = sfac_data['Link']
            # If time says cancelled on site, honor it
            if "CANCEL" in sfac_data['Time'].upper(): m['DisplayTime'] = "CANCELLED"
    
    # Fallback to Hardcoded LIS link if no API link
    backup_link = construct_backup_link(m.get("OwnerName"))
    
    final_link = api_link if api_link else backup_link
    m['Link'] = final_link
    m['LinkSource'] = "API/Site" if api_link else "Backup"
    
    if final_link:
        links_to_scan.append(final_link)
        
    processed_events.append(m)

# Auto-Scan Bills
bill_cache = {}
if links_to_scan:
    unique_links = list(set(links_to_scan))
    with st.spinner(f"Diving {len(unique_links)} Dockets..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(get_bills_deep_dive, url): url for url in unique_links}
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
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
