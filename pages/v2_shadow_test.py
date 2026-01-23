import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v54 Network Inspector", page_icon="📡", layout="wide")
st.title("📡 v54: The 'Network Inspector' & Targeted Fetch")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- GLOBAL LOGS ---
if 'network_logs' not in st.session_state: st.session_state.network_logs = []

def log_network(source, url, status, snippet):
    st.session_state.network_logs.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "source": source,
        "url": url,
        "status": status,
        "snippet": snippet
    })

# --- HELPER: DNA & TIME ---
def get_dna_tokens(text):
    if not text: return set()
    lower = text.lower()
    lower = lower.replace(".ics", "").replace("view agenda", "")
    lower = re.sub(r'[^a-z0-9\s#]', '', lower)
    tokens = set(lower.split())
    generic_dna = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "a", "an", "agenda", "view", 
        "video", "public", "testimony", "bill", "caucus", "general", 
        "assembly", "commonwealth", "session", "adjourned"
    }
    return tokens - generic_dna

def parse_time_string(text):
    if not text: return None
    clean = text.lower().strip()
    if "cancel" in clean: return "❌ Cancelled"
    if "noon" in clean: return "12:00 PM"
    
    # Check for "Upon Adjournment"
    if "adj" in clean or "convenes" in clean:
        # Return the whole phrase if it's short, or a summary
        return text.strip()
        
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', text)
    if match: return match.group(1).upper()
    return None

# --- SOURCE 1: TARGETED AGENDA SCRAPE (The Sniper) ---
def fetch_agenda_time(url):
    """
    Visits a specific committee agenda page to find the time.
    """
    try:
        resp = session.get(url, timeout=3)
        log_network("Agenda Probe", url, resp.status_code, resp.text[:100])
        
        if resp.status_code != 200: return None
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Look for "Time: 9:00 AM" or similar patterns
        # or "Meeting Time: ..."
        
        # 1. Strict Regex
        match = re.search(r'(?:Time|Start):\s*(\d{1,2}:\d{2}\s*[aA|pP]?[mM]?)', text, re.IGNORECASE)
        if match: return match.group(1)
        
        # 2. Loose Time Scan
        return parse_time_string(text[:500]) # Check header area
        
    except Exception as e:
        log_network("Agenda Probe", url, "ERROR", str(e))
        return None

# --- SOURCE 2: HOUSE SCHEDULE (The Dragnet) ---
@st.cache_data(ttl=300)
def fetch_house_schedule():
    schedule_map = {} 
    st.session_state.network_logs = [] # Clear logs on refresh
    
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() if today.weekday() > 0 else 0 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    
    # We test multiple date formats to see which one sticks
    urls = [
        ("Current Week", "https://house.vga.virginia.gov/schedule/meetings"),
        ("Next Week (US)", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%m/%d/%Y')}"),
        ("Next Week (ISO)", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%Y-%m-%d')}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # CHECK: Did we actually get the date we asked for?
            page_text = soup.get_text()
            date_found = "Unknown"
            match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', page_text)
            if match: date_found = match.group(0)
            
            log_network(f"House ({label})", url, resp.status_code, f"Date Found: {date_found}")
            
            # Parse Blocks
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
                        # Flush old
                        if current_date and current_block:
                            if current_date not in schedule_map: schedule_map[current_date] = []
                            schedule_map[current_date].append("\n".join(current_block))
                            current_block = []
                        
                        # Parse Date
                        try:
                            raw_s = f"{d_match.group(0)} 2026"
                            current_date = datetime.strptime(raw_s, "%A, %B %d %Y").date()
                        except: pass
                        continue
                
                if not current_date: continue
                
                # Block Delimiters
                low = text.lower()
                if "convenes" in low or "session" in low:
                    if current_block:
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append("\n".join(current_block))
                        current_block = []
                
                current_block.append(text)
                
                if ".ics" in low or "archived" in low:
                    if current_block:
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append("\n".join(current_block))
                        current_block = []
                        
            # Flush final
            if current_date and current_block:
                if current_date not in schedule_map: schedule_map[current_date] = []
                schedule_map[current_date].append("\n".join(current_block))
                
        except Exception as e:
            log_network(f"House ({label})", url, "ERROR", str(e))
            
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

with st.spinner("Fetching Schedule & Auditing Network..."):
    all_meetings = get_full_schedule()
    house_blocks_map = fetch_house_schedule()

# --- NETWORK INSPECTOR TAB ---
tab_cal, tab_net = st.tabs(["📅 Calendar", "🕵️ Network Inspector"])

with tab_net:
    st.subheader("📡 Scraper Network Logs")
    st.info("This table proves if the server is actually returning the 'Next Week' data.")
    st.dataframe(st.session_state.network_logs, use_container_width=True)

with tab_cal:
    # --- CALENDAR LOGIC ---
    today = datetime.now().date()
    week_map = {}
    for i in range(8): week_map[today + timedelta(days=i)] = []

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
        
        # 1. API COMMENTS (Best Source)
        if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
            final_time = api_comments
            match_source = "API Comments"
        
        # 2. HOUSE SCHEDULE SCRAPER (Broad Scan)
        elif m_date in house_blocks_map:
            blocks = house_blocks_map[m_date]
            api_dna = get_dna_tokens(name)
            
            for block_text in blocks:
                block_dna = get_dna_tokens(block_text)
                if api_dna.issubset(block_dna):
                    t = parse_time_string(block_text)
                    if t: 
                        final_time = t
                        match_source = "House Scraper (DNA)"
                        break
        
        # 3. AGENDA PROBE (Last Resort for Next Week)
        # If we still don't have a time, and it's missing, try the specific link
        if "Not Listed" in final_time and m.get("Description"):
            link = extract_agenda_link(m.get("Description"))
            if link:
                t = fetch_agenda_time(link)
                if t:
                    final_time = t
                    match_source = "Agenda Probe (Direct)"

        # Fallback to API generic time
        if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
            final_time = api_time 
            match_source = "API Generic"

        m['DisplayTime'] = final_time
        m['CleanDate'] = m_date
        m['AgendaLink'] = extract_agenda_link(m.get("Description"))
        m['MatchSource'] = match_source
        
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
                        
                        if "Not Listed" in time_str:
                             st.caption(f"Source: {m['MatchSource']}")
