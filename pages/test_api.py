import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v103 API Merge", page_icon="🏛️", layout="wide")
st.title("🏛️ v103: The API-Only Merge")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

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

def extract_link_from_description(desc_text):
    """
    Regex pull for href="..." inside the Description field.
    """
    if not desc_text: return None
    # Look for http/https URLs inside href tags or plain text
    match = re.search(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    if match: return match.group(1)
    
    # Fallback: Just look for a raw URL
    raw_match = re.search(r'(https?://house.vga.virginia.gov[^\s]+)', desc_text)
    if raw_match: return raw_match.group(1)
    
    return None

def get_bills_from_url(url):
    """
    Scrapes bills from a target URL.
    """
    if not url: return []
    try:
        # We use a standard request here as these pages are usually open
        resp = requests.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for Bill IDs (HB100, SB50)
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
    except:
        return []

# --- 1. GET SCHEDULE (API) ---
@st.cache_data(ttl=600)
def fetch_api_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    events = []
    try:
        # Fetch House & Senate
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            for f in [h, s]:
                if f.result().status_code == 200:
                    events.extend(f.result().json().get("Schedules", []))
    except: pass
    return events

# --- MAIN APP LOGIC ---

with st.spinner("Fetching Schedule API..."):
    raw_events = fetch_api_schedule()

today = datetime.now().date()
processed_events = []
links_to_scan = []

# 1. PROCESS EVENTS
for m in raw_events:
    # Filter Date
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    # Filter Type (Committee = 1, we can optionally keep others)
    # m['ScheduleTypeID']
    
    # Extract Data
    m['DateObj'] = d
    m['DisplayTime'] = m.get("ScheduleTime", "TBA")
    
    # CHECK CANCELLATION (API FIELD)
    # The autopsy showed "IsCancelled": false/true
    if m.get("IsCancelled") is True:
        m['DisplayTime'] = "CANCELLED"
    
    # EXTRACT LINK (FROM DESCRIPTION)
    m['Link'] = extract_link_from_description(m.get("Description"))
    
    # If we have a link, queue it for scanning
    if m['Link']:
        links_to_scan.append(m['Link'])
        
    processed_events.append(m)

# 2. SCAN BILLS (Parallel)
bill_cache = {}
if links_to_scan:
    # Deduplicate links
    unique_links = list(set(links_to_scan))
    with st.spinner(f"Scanning {len(unique_links)} Dockets..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_url = {executor.submit(get_bills_from_url, url): url for url in unique_links}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    bill_cache[url] = future.result()
                except:
                    bill_cache[url] = []

# 3. GROUP BY DATE & DISPLAY
display_map = {}
for m in processed_events:
    d = m['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

if not display_map:
    st.info("No upcoming events found in API.")
else:
    sorted_dates = sorted(display_map.keys())[:7] # Next 7 active days
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
                # Clean Name
                clean_name = name.replace("Committee", "").replace("Virginia", "").strip()
                
                time_disp = event.get("DisplayTime")
                link = event.get("Link")
                bills = bill_cache.get(link, [])
                
                # Check Cancelled
                is_cancelled = "CANCEL" in str(time_disp).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{clean_name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        # Time Header
                        if "TBA" in str(time_disp) or "Not Listed" in str(time_disp):
                            st.warning(f"⚠️ {time_disp}")
                        else:
                            st.markdown(f"**⏰ {time_disp}**")
                        
                        # Name
                        st.markdown(f"**{clean_name}**")
                        
                        # Bills / Action
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View List"):
                                st.write(", ".join(bills))
                                if link: st.link_button("View Docket", link)
                        elif link:
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
