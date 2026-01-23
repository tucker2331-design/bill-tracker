import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v55 Agenda Sniper", page_icon="🎯", layout="wide")
st.title("🎯 v55: The 'Agenda Sniper'")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

# --- HELPER: DNA & TIME ---
def get_dna_tokens(text):
    if not text: return set()
    lower = text.lower()
    lower = lower.replace(".ics", "").replace("view agenda", "")
    lower = re.sub(r'[^a-z0-9\s#]', '', lower)
    tokens = set(lower.split())
    
    # CRITICAL FIX: If the name is very short (e.g. "House Convenes"), 
    # DO NOT filter generic words. We need them.
    if len(tokens) <= 3:
        return tokens
        
    generic_dna = {
        "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "a", "an", "agenda", "view", 
        "video", "public", "testimony", "bill", "caucus", "general", 
        "assembly", "commonwealth", "adjourned"
        # "House", "Senate", "Session", "Convenes" REMOVED from filter to fix regression
    }
    return tokens - generic_dna

def parse_time_string(text):
    if not text: return None
    clean = text.lower().strip()
    if "cancel" in clean: return "❌ Cancelled"
    if "noon" in clean: return "12:00 PM"
    
    if "adj" in clean or "convenes" in clean:
        return text.strip()
        
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', text)
    if match: return match.group(1).upper()
    return None

# --- SOURCE 1: AGENDA SNIPER (The Fix) ---
def scrape_agenda_for_time(agenda_url):
    """
    Visits the agenda page directly to find the time.
    """
    if not agenda_url: return None
    try:
        # Fast timeout - if it's slow, skip it
        resp = session.get(agenda_url, timeout=2)
        if resp.status_code != 200: return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for "Time: 9:00 AM" or "Meeting Time: 9:00 AM"
        # Most Virginia agendas have this at the top
        match = re.search(r'(?:Time|Start|Convening):\s*(\d{1,2}:\d{2}\s*[aA|pP]?[mM]?)', text, re.IGNORECASE)
        if match: 
            return match.group(1).upper()
            
        # Fallback: Look for just a standalone time at the very top
        header_text = text[:300]
        t = parse_time_string(header_text)
        if t and "Listed" not in t: return t
        
        return None
    except: return None

# --- SOURCE 2: HOUSE SCHEDULE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_house_schedule():
    schedule_map = {} 
    
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() if today.weekday() > 0 else 0 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    
    # We know this works now based on the logs
    urls = [
        ("Current", "https://house.vga.virginia.gov/schedule/meetings"),
        ("Next", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%m/%d/%Y')}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            all_tags = soup.find_all(['div', 'span', 'p', 'h4', 'h5', 'a', 'li'])
            current_date = None
            current_block = []
            
            for tag in all_tags:
                text = tag.get_text(" ", strip=True)
                if not text: continue
                
                # Date Header
                if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                    d_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                    if d_match:
                        if current_date and current_block:
                            if current_date not in schedule_map: schedule_map[current_date] = []
                            schedule_map[current_date].append("\n".join(current_block))
                            current_block = []
                        
                        try:
                            raw_s = f"{d_match.group(0)} 2026"
                            current_date = datetime.strptime(raw_s, "%A, %B %d %Y").date()
                        except: pass
                        continue
                
                if not current_date: continue
                
                # Parsing Blocks - Less aggressive splitting
                low = text.lower()
                is_end = ".ics" in low or "archived" in low
                
                current_block.append(text)
                
                if is_end:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append("\n".join(current_block))
                    current_block = []
                        
            if current_date and current_block:
                if current_date not in schedule_map: schedule_map[current_date] = []
                schedule_map[current_date].append("\n".join(current_block))
                
        except: pass
            
    return schedule_map

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
    house_blocks_map = fetch_house_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. PRE-PROCESS: Identify which meetings need the "Agenda Sniper"
# This avoids doing it one-by-one in the loop
sniper_tasks = []
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    api_time = m.get("ScheduleTime")
    agenda_link = extract_agenda_link(m.get("Description"))
    
    # If API time is missing/generic AND we have a link -> Add to Sniper Queue
    if (not api_time or "12:00" in str(api_time) or "TBA" in str(api_time)) and agenda_link:
        sniper_tasks.append((m['ScheduleID'], agenda_link))

# 2. EXECUTE SNIPER (Parallel Fetch)
sniper_results = {}
if sniper_tasks:
    with st.spinner(f"🎯 Sniping {len(sniper_tasks)} Agendas for exact times..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_id = {executor.submit(scrape_agenda_for_time, url): mid for mid, url in sniper_tasks}
            for future in concurrent.futures.as_completed(future_to_id):
                mid = future_to_id[future]
                try: sniper_results[mid] = future.result()
                except: sniper_results[mid] = None

# 3. BUILD DISPLAY
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
    
    # PRIORITY 1: API COMMENTS
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
        
    # PRIORITY 2: AGENDA SNIPER (The New Fix)
    elif m['ScheduleID'] in sniper_results and sniper_results[m['ScheduleID']]:
        final_time = sniper_results[m['ScheduleID']]
        
    # PRIORITY 3: HOUSE SCRAPER (Fallback)
    elif m_date in house_blocks_map:
        blocks = house_blocks_map[m_date]
        api_dna = get_dna_tokens(name)
        
        for block_text in blocks:
            block_dna = get_dna_tokens(block_text)
            # DNA Match
            if api_dna.issubset(block_dna):
                t = parse_time_string(block_text)
                if t: 
                    final_time = t
                    break
    
    # FALLBACK
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    week_map[m_date].append(m)

# --- RENDER ---
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
