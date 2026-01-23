import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v57 Table-Aware", page_icon="🏗️", layout="wide")
st.title("🏗️ v57: The 'Table-Aware' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    lower = text.lower()
    
    # Clean noise but KEEP numbers and letters and #
    lower = lower.replace(".ics", "").replace("view agenda", "")
    lower = re.sub(r'[^a-z0-9\s#]', '', lower)
    
    tokens = set(lower.split())
    
    # Filter out generic noise
    # We KEEP "committee", "subcommittee", "house", "senate" to ensure correct entity match
    generic_noise = {
        "room", "building", "meeting", "the", "of", "and", "a", "an", 
        "agenda", "view", "video", "public", "testimony", "bill", 
        "caucus", "general", "assembly", "commonwealth", "session"
    }
    return tokens - generic_noise

def extract_relative_time(block_text):
    """
    Catches "Upon adjournment" patterns first, then clock times.
    """
    lower = block_text.lower()
    
    # 1. Relative Patterns (High Priority)
    keywords = ["adjournment", "adjourn", "upon", "immediate", "rise of", "recess", "after"]
    lines = block_text.split('\n')
    for line in lines:
        l_low = line.lower()
        if any(k in l_low for k in keywords):
            return line.strip()
            
    # 2. Clock Time (Fallback)
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', block_text)
    if match: return match.group(1).upper()
    
    return None

# --- SCRAPER: HOUSE SCHEDULE ---
@st.cache_data(ttl=300)
def fetch_house_schedule():
    schedule_map = {} 
    
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() if today.weekday() > 0 else 0 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    
    # Fetch Current + Next Week
    urls = [
        ("Current", "https://house.vga.virginia.gov/schedule/meetings"),
        ("Next", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%m/%d/%Y')}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # CRITICAL FIX: Added 'td', 'tr', 'tbody' to the search list
            # This ensures we see text inside tables.
            all_tags = soup.find_all(['div', 'span', 'p', 'h4', 'h5', 'a', 'li', 'td', 'tr'])
            
            current_date = None
            current_block = []
            
            for tag in all_tags:
                text = tag.get_text(" ", strip=True)
                if not text: continue
                
                # DATE HEADER DETECTION
                if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                    d_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                    if d_match:
                        # Flush previous
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
                
                # BLOCK DELIMITERS
                low = text.lower()
                
                # Start new block on "Convenes" or "Session"
                if "convenes" in low or "session" in low:
                    if current_block:
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append("\n".join(current_block))
                        current_block = []
                
                current_block.append(text)
                
                # End block on .ics
                if ".ics" in low or "archived" in low:
                    if current_block:
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append("\n".join(current_block))
                        current_block = []
                        
            # Flush final
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

with st.spinner("Processing..."):
    all_meetings = get_full_schedule()
    house_blocks_map = fetch_house_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

# Sort: Long names first (Specific Subcommittees) to avoid matching generic parents
all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

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
    match_source = "None"
    
    # 1. API COMMENTS
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
        match_source = "API"
        
    # 2. HOUSE SCRAPER (Checklist Logic)
    elif m_date in house_blocks_map:
        blocks = house_blocks_map[m_date]
        api_tokens = get_clean_tokens(name)
        
        for block_text in blocks:
            block_tokens = get_clean_tokens(block_text)
            
            # CHECKLIST: ALL API tokens must exist in the block tokens
            # This allows the block to have extra words (like Chair name)
            if api_tokens and api_tokens.issubset(block_tokens):
                t = extract_relative_time(block_text)
                if t: 
                    final_time = t
                    match_source = "Scraper (Table)"
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
