import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v26 Token Consumer", page_icon="🧶", layout="wide")
st.title("🧶 v26: The 'Token Consumer' (Duplicate Fix)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    """Turns 'House General Laws - Professions' into {'general', 'laws', 'professions'}"""
    if not text: return set()
    # Words to remove to get to the "core identity"
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "-", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus"
    }
    # Clean, lowercase, split
    words = set(re.sub(r'[^a-zA-Z\s]', '', text.lower()).split())
    return words - noise

def is_time_string(line):
    """Checks if a line looks like a time instruction"""
    l = line.lower()
    if "adjourn" in l or "recess" in l or "upon" in l or "immediately" in l or "after" in l: return True
    if re.search(r'\d{1,2}:\d{2}', l) and ("am" in l or "pm" in l or "noon" in l): return True
    return False

# --- COMPONENT 1: THE FLAT SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_daily_text_lines():
    """
    Returns a map: { DateObject: [ {"id": 1, "text": "Line 1"}, ... ] }
    We give each line an ID so we can 'consume' it later.
    """
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        text_blob = soup.get_text("\n")
        raw_lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        current_date = None
        
        for i, line in enumerate(raw_lines):
            # 1. Detect Date Header
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    clean_date = line.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                    if current_date not in schedule_map: schedule_map[current_date] = []
                except: pass
                continue
            
            # 2. Add line with ID
            if current_date:
                schedule_map[current_date].append({
                    "id": i,
                    "text": line,
                    "tokens": get_clean_tokens(line),
                    "used": False # Track consumption
                })
                    
    except Exception as e: pass
    return schedule_map

# --- COMPONENT 2: API FETCH (Source A) ---
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
        
    unique_items = []
    seen = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen:
            seen.add(sig)
            unique_items.append(m)
    return unique_items

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if any(x in link.get_text().lower() for x in ["agenda", "committee info", "docket"]):
            return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills: clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        def natural_sort_key(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
        return sorted(list(clean_bills), key=natural_sort_key)
    except: return []

def fetch_bills_parallel(meetings_list):
    tasks = []
    for m in meetings_list:
        if m.get('AgendaLink'): tasks.append((m, m['AgendaLink']))
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(scan_agenda_page, url): m['ScheduleID'] for m, url in tasks}
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try: results[mid] = future.result()
            except: results[mid] = []
    return results

def parse_time_rank(time_str):
    if not time_str: return 9999
    clean = time_str.lower().replace(".", "").strip()
    if "adjourn" in clean or "recess" in clean or "upon" in clean or "after" in clean: return 960 
    if "tba" in clean: return 9999
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

if st.button("🚀 Run Token-Consumer Forecast"):
    
    with st.spinner("Fetching API Schedule..."):
        all_meetings = get_full_schedule()
        
    with st.spinner("Scraping Text Lines..."):
        daily_lines_map = fetch_daily_text_lines()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7): week_map[today + timedelta(days=i)] = []
    valid_meetings = []
    
    # PRE-SORT MEETINGS to prioritize subcommittees (more specific) before parents
    # This helps matching "Subcommittee #1" before matching generic "Appropriations"
    all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            # --- THE CONSUMER LOGIC ---
            api_time = m.get("ScheduleTime")
            api_comments = m.get("Comments") or ""
            
            final_time = api_time
            
            # 1. Check API Comments
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            # 2. If API fails, SCAN THE TEXT LINES
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                if m_date in daily_lines_map:
                    lines = daily_lines_map[m_date]
                    api_tokens = get_clean_tokens(name)
                    
                    found_match_index = -1
                    
                    # Find matching line
                    for i, line_obj in enumerate(lines):
                        if line_obj['used']: continue # Skip lines we already matched!
                        
                        web_tokens = line_obj['tokens']
                        
                        # MATCH: Check if all API core words exist in Web line
                        # e.g. API={general, laws} in Web={general, laws, professions} -> MATCH
                        if api_tokens and api_tokens.issubset(web_tokens):
                            found_match_index = i
                            line_obj['used'] = True # MARK CONSUMED
                            break
                            
                    # If match found, look down for time
                    if found_match_index != -1:
                        for offset in range(1, 6):
                            if found_match_index + offset >= len(lines): break
                            
                            candidate = lines[found_match_index + offset]['text']
                            
                            if is_time_string(candidate):
                                final_time = candidate
                                break

            # 3. Fallback
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
                
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings: m['Bills'] = bill_results.get(m['ScheduleID'], [])

    cols = st.columns(7)
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
                    bill_count = len(m.get('Bills', []))
                    full_name = m.get("OwnerName", "")
                    parent_name, sub_name = parse_committee_name(full_name)
                    
                    time_str = m['DisplayTime']
                    if len(time_str) > 50: time_str = "See Details"
                    
                    with st.container(border=True):
                        if len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
                        else: st.markdown(f"**{time_str}**")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
