import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v104 Link Router", page_icon="🔀", layout="wide")
st.title("🔀 v104: The 'Link Router' (Fixing Generic Buttons)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- THE LINK ROUTER (The Fix) ---
# Maps generic "Marketing URLs" to data-rich "LIS URLs"
LINK_MAP = {
    # HOUSE COMMITTEES (Marketing -> LIS ID)
    "hac.virginia.gov": "https://house.vga.virginia.gov/committees/H02", # Appropriations
    "house.virginia.gov": "https://house.vga.virginia.gov/committees/H09", # Finance (Generic Fallback)
    
    # SENATE COMMITTEES (Marketing -> LIS ID)
    "sfac.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S05", # Finance
    "commerce.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S03", # Commerce
    "courts.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S04", # Courts
    "education.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S02", # Ed & Health
    "general.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S06", # General Laws
    "local.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S07", # Local Gov
    "privileges.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S08", # Privileges
    "rehab.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S09", # Rehab
    "transportation.senate.virginia.gov": "https://lis.virginia.gov/cgi-bin/legp604.exe?261+com+S10", # Transportation
}

def route_link(original_link):
    """
    Swaps generic links for specific ones using the map.
    """
    if not original_link: return None, "None"
    
    # Check if any key is in the URL
    for marketing_key, deep_url in LINK_MAP.items():
        if marketing_key in original_link.lower():
            return deep_url, "Swapped"
            
    return original_link, "Original"

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
    if not desc_text: return None
    match = re.search(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    if match: return match.group(1)
    raw_match = re.search(r'(https?://house.vga.virginia.gov[^\s]+)', desc_text)
    if raw_match: return raw_match.group(1)
    return None

def get_bills_from_url(url):
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

with st.spinner("Fetching Schedule & Routing Links..."):
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
    
    if m.get("IsCancelled") is True:
        m['DisplayTime'] = "CANCELLED"
    
    # 1. Extract Raw Link
    raw_link = extract_link_from_description(m.get("Description"))
    
    # 2. ROUTE LINK (The Middleware)
    final_link, link_status = route_link(raw_link)
    
    m['Link'] = final_link
    m['LinkStatus'] = link_status
    m['RawLink'] = raw_link
    
    if m['Link']:
        links_to_scan.append(m['Link'])
        
    processed_events.append(m)

# Scan Bills
bill_cache = {}
if links_to_scan:
    unique_links = list(set(links_to_scan))
    with st.spinner(f"Scanning {len(unique_links)} Dockets..."):
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
                status = event.get("LinkStatus")
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
                            label = "📄 View Docket" if status == "Swapped" else "🔗 View Link"
                            st.link_button(label, link)
                        else:
                            st.caption("*(No Link)*")
                        
                        if status == "Swapped":
                            st.caption("ℹ️ Link Auto-Corrected")
