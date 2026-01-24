import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v61 Agenda Reader", page_icon="📖", layout="wide")
st.title("📖 v61: The 'Agenda Reader' (Relative Time Fix)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def extract_time_from_text(text):
    """
    Parses text to find either clock times OR relative phrases.
    """
    if not text: return None
    clean = text.strip()
    lower = clean.lower()
    
    # 1. PRIORITY: Relative Phrases (The Fix for 'Yellow' meetings)
    # Catches: "Immediately upon adjournment", "15 mins after", "Upon recess"
    relative_keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of"
    ]
    
    # If the text block is short (like a header), check the whole thing
    if len(clean) < 150:
        if any(k in lower for k in relative_keywords):
            return clean.strip()
            
    # If text is long, scan line by line
    for line in clean.splitlines():
        l_low = line.lower()
        if any(k in l_low for k in relative_keywords):
            return line.strip()

    # 2. FALLBACK: Clock Times (e.g. 9:00 AM)
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

# --- SOURCE 1: AGENDA READER ---
def scrape_agenda(url):
    """
    Visits the specific agenda URL provided by the API.
    """
    if not url: return None
    try:
        # Fast timeout. If it hangs, we skip.
        resp = session.get(url, timeout=3)
        if resp.status_code != 200: return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Strategy: Look for the Header section where time is usually listed
        # This is often in the first 500 characters of text
        full_text = soup.get_text(" ", strip=True)
        header_text = full_text[:1000] # Scan first 1000 chars
        
        # 1. Look for explicit labels "Time: ..."
        match = re.search(r'(?:Time|Start|Convening):\s*(.*?)(?:Place|Location|$)', header_text, re.IGNORECASE)
        if match:
            # We found a label! Now extract the time/phrase from it.
            raw_time_str = match.group(1)
            parsed = extract_time_from_text(raw_time_str)
            if parsed: return parsed
            
        # 2. Loose Scan of the header
        # If no "Time:" label, just look for the phrases anywhere in the top section
        parsed = extract_time_from_text(header_text)
        if parsed: return parsed
        
        return None
        
    except: return None

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    raw_items = []
    
    def fetch_chamber(chamber):
        try:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = session.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("Schedules", [])
                for item in data: item['Chamber'] = chamber
                return data
        except: return []
        return []
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(fetch_chamber, ["H", "S"])
        for r in results: raw_items.extend(r)
        
    unique = []
    seen = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen:
            seen.add(sig)
            unique.append(m)
    return unique

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if any(x in link.get_text().lower() for x in ["agenda", "committee info", "docket"]):
            return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def parse_time_rank(time_str):
    if not time_str or "Not Listed" in time_str or "TBA" in time_str: return 9999
    if "Cancelled" in time_str: return 9998
    clean = time_str.lower().replace(".", "").strip()
    if "adjourn" in clean or "recess" in clean or "upon" in clean or "after" in clean: return 960 
    try:
        dt = datetime.strptime(clean, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except: return 9999 

def parse_committee_name(full_name):
    if " - " in full_name:
        parts = full_name.split(" - ", 1)
        return parts[0], parts[1]
    elif "Subcommittee" in full_name:
        return full_name, None
    return full_name, None

# --- MAIN UI ---

with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. IDENTIFY MISSING TIMES (The "Yellow" Ones)
# We only want to scrape agendas for meetings that DON'T have a time.
tasks = []
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    api_time = m.get("ScheduleTime")
    agenda_link = extract_agenda_link(m.get("Description"))
    
    # If time is missing/generic AND we have a link -> Add to Queue
    if (not api_time or "12:00" in str(api_time) or "TBA" in str(api_time)) and agenda_link:
        tasks.append((m['ScheduleID'], agenda_link))

# 2. BATCH PROCESS (Parallel Fetching)
agenda_results = {}
if tasks:
    st.toast(f"Reading {len(tasks)} agendas to find missing times...", icon="📖")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(scrape_agenda, url): mid for mid, url in tasks}
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try: agenda_results[mid] = future.result()
            except: agenda_results[mid] = None

# 3. RENDER
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    final_time = "⚠️ Not Listed on Schedule"
    
    # Priority 1: API Comments
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
    
    # Priority 2: Agenda Reader (New Fix)
    elif m['ScheduleID'] in agenda_results and agenda_results[m['ScheduleID']]:
        final_time = agenda_results[m['ScheduleID']]
        
    # Priority 3: API Time (The Working 2/3rds)
    elif api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    week_map[m_date].append(m)

# --- DISPLAY ---
cols = st.columns(len(week_map)) 
days = sorted(week_map.keys())

for i, day in enumerate(days):
    with cols[i]:
        st.markdown(f"### {day.strftime('%a')}")
        st.caption(day.strftime('%b %d'))
        st.divider()
        daily_meetings = week_map[day]
        daily_meetings.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
        
        if not daily_meetings:
            st.info("No Committees")
        else:
            for m in daily_meetings:
                full_name = m.get("OwnerName", "")
                parent_name, sub_name = parse_committee_name(full_name)
                time_str = m['DisplayTime']
                if len(time_str) > 60: time_str = "See Details"
                
                with st.container(border=True):
                    if "Not Listed" in time_str: st.warning(f"{time_str}")
                    elif "Time Not Listed" in time_str: st.info(f"{time_str}")
                    elif "Cancelled" in time_str: st.error(f"{time_str}")
                    elif len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
                    else: st.markdown(f"**{time_str}**")
                    
                    st.markdown(f"**{parent_name}**")
                    if sub_name: st.caption(f"↳ *{sub_name}*")
                            
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
