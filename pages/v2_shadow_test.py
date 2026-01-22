import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v34 Final Logic", page_icon="🏁", layout="wide")
st.title("🏁 v34: The Cancellation-Aware Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG TOGGLE ---
debug_mode = st.sidebar.checkbox("🐞 Match Debugger", value=False)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    # Handle specific artifacts seen in screenshots
    clean_text = text.lower().replace(".ics", "").replace("view agenda", "")
    clean_text = clean_text.replace("-", " ").replace("#", " ")
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus",
        "general", "assembly", "commonwealth", "new", "time", "changed", "meeting"
    }
    return set(clean_text.split()) - noise

def extract_time_from_block(block_text):
    """Scans a raw block of text for time indicators OR cancellations."""
    lower_text = block_text.lower()
    
    # 1. CANCELLATION CHECK (High Priority)
    if "cancel" in lower_text:
        return "❌ Cancelled"

    # 2. Look for specific phrases (Medium Priority)
    phrases = [
        "immediately upon adjournment", "upon adjournment", "1/2 hour after adjournment", 
        "15 minutes after adjournment", "recess", "after adjournment"
    ]
    for p in phrases:
        if p in lower_text:
            # Try to return the whole line containing the phrase for context
            for line in block_text.splitlines():
                if p in line.lower(): return line.strip()
            return p.title()

    # 3. Look for standard times (Low Priority)
    # Regex for "7:00 AM" or "10:00 a.m."
    time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', block_text)
    if time_match:
        return time_match.group(1).upper()
        
    return None

# --- COMPONENT 1: THE BLOCK SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_daily_blocks():
    """
    Returns: { DateObject: [ "Raw Block Text 1", "Raw Block Text 2" ] }
    Splits the page by '.ics' to create distinct meeting buckets.
    """
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        text_blob = soup.get_text("\n")
        
        # 1. SPLIT BY DATE HEADERS FIRST
        lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        current_date = None
        current_block_lines = []
        
        for line in lines:
            # Date Detection
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2})', line)
                    if match:
                        # Flush previous block
                        if current_date and current_block_lines:
                            schedule_map[current_date].append("\n".join(current_block_lines))
                            current_block_lines = []
                            
                        clean_date_str = f"{match.group(0)} 2026"
                        dt = datetime.strptime(clean_date_str, "%A, %B %d %Y")
                        current_date = dt.date()
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        continue
                except: pass
            
            if not current_date: continue
            
            # Add line to current block
            current_block_lines.append(line)
            
            # END OF BLOCK DETECTOR (.ics)
            # ".ics" or "Archived" ends a meeting card
            if ".ics" in line.lower() or "archived" in line.lower():
                schedule_map[current_date].append("\n".join(current_block_lines))
                current_block_lines = []
                
        # Flush last block
        if current_date and current_block_lines:
            schedule_map[current_date].append("\n".join(current_block_lines))
            
    except Exception as e: pass
    return schedule_map

# --- COMPONENT 2: API FETCH ---
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

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean = set()
        for p, n in bills: clean.add(f"{p.upper().replace('.','').strip()}{n}")
        def n_sort(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
        return sorted(list(clean), key=n_sort)
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
    if not time_str or "Not Listed" in time_str or "TBA" in time_str: return 9999
    if "Cancelled" in time_str: return 9998 # Cancelled at bottom
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

if st.button("🚀 Run Final Forecast"):
    
    with st.spinner("Fetching API..."):
        all_meetings = get_full_schedule()
        daily_blocks_map = fetch_daily_blocks()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7): week_map[today + timedelta(days=i)] = []
    valid_meetings = []
    
    # Sort API items: Longest names first (Specific Subcommittees > Generic Parents)
    all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            api_time = m.get("ScheduleTime")
            api_comments = m.get("Comments") or ""
            
            # Default State: ASSUME NOT LISTED unless proven otherwise
            final_time = "⚠️ Not Listed on Schedule"
            match_debug = []
            
            # 1. API Comments Authority (e.g. "Upon Adjournment")
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            # 2. Block Search
            elif m_date in daily_blocks_map:
                blocks = daily_blocks_map[m_date]
                api_tokens = get_clean_tokens(name)
                
                best_block = None
                best_score = 0.0
                
                for block_text in blocks:
                    block_tokens = get_clean_tokens(block_text)
                    intersection = api_tokens.intersection(block_tokens)
                    
                    if not intersection: continue
                    
                    # Scoring
                    score = len(intersection) / len(api_tokens)
                    
                    # Bonus for Numbers ("#1", "#2") - CRITICAL
                    numbers = {'1','2','3','4','5','6'}
                    if intersection.intersection(numbers): score += 0.5
                    
                    match_debug.append(f"{score:.2f}: {block_text[:30]}...")
                    
                    if score > best_score and score > 0.65:
                        best_score = score
                        best_block = block_text
                
                if best_block:
                    # FOUND THE BLOCK! Extract time or CANCELLATION
                    extracted_time = extract_time_from_block(best_block)
                    if extracted_time:
                        final_time = extracted_time
                    else:
                        final_time = "Time Not Listed" # Found block, but no time
            
            # If API had a valid time (not 12:00/TBA) and we didn't find a better one...
            # BUT check if we found a "Not Listed" state.
            if "Not Listed" in final_time:
                # Only fallback to API if API has a REAL time (not default)
                if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
                    final_time = api_time 

            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            m['ApiTokens'] = get_clean_tokens(name)
            m['DebugInfo'] = sorted(match_debug, reverse=True)[:5]
            
            # Optional: Hide "Not Listed" meetings completely?
            # if "Not Listed" in final_time: continue 
            
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
                    if len(time_str) > 60: time_str = "See Details"
                    
                    with st.container(border=True):
                        # TIME / STATUS DISPLAY
                        if "Cancelled" in time_str:
                            st.error(f"{time_str}") # Red Box for Cancelled
                        elif "Not Listed" in time_str:
                            st.warning(f"{time_str}") # Yellow for Ghost
                        elif "Time Not Listed" in time_str:
                            st.info(f"{time_str}") # Blue for Found but Empty
                        elif len(time_str) > 15: 
                            st.caption(f"🕒 *{time_str}*") 
                        else: 
                            st.markdown(f"**{time_str}**")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        if debug_mode and "Not Listed" in time_str:
                            st.caption(f"Tokens: {m['ApiTokens']}")
                            for d in m.get('DebugInfo', []): st.text(d)

                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
