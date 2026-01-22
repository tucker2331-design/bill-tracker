import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v27 Match X-Ray", page_icon="🩻", layout="wide")
st.title("🩻 v27: The Match X-Ray (Hyphen Fix + Debugger)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG STORAGE ---
debug_info = {} # Stores match attempts for the UI

# --- HELPER: TEXT CLEANING (THE FIX) ---
def get_clean_tokens(text):
    """
    Turns 'House General Laws-Professions' into {'general', 'laws', 'professions'}
    CRITICAL FIX: Replaces hyphens with spaces first!
    """
    if not text: return set()
    
    # 1. Replace hyphens with spaces so "Laws-Professions" becomes "Laws Professions"
    clean_text = text.replace("-", " ").lower()
    
    # 2. Remove non-alpha characters
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    # 3. Define Noise Words
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus",
        "general", "assembly" # Added "general assembly" as noise since it appears in addresses
    }
    
    words = set(clean_text.split())
    return words - noise

def is_time_string(line):
    l = line.lower()
    if "adjourn" in l or "recess" in l or "upon" in l or "immediately" in l or "after" in l: return True
    if re.search(r'\d{1,2}:\d{2}', l) and ("am" in l or "pm" in l or "noon" in l): return True
    return False

# --- COMPONENT 1: THE FLAT SCRAPER ---
@st.cache_data(ttl=300)
def fetch_daily_text_lines():
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
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    clean_date = line.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                    if current_date not in schedule_map: schedule_map[current_date] = []
                except: pass
                continue
            
            if current_date:
                # Store full context for debugging
                schedule_map[current_date].append({
                    "id": i,
                    "text": line,
                    "tokens": get_clean_tokens(line),
                    "used": False
                })
                    
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

# SIDEBAR DEBUG TOGGLE
debug_mode = st.sidebar.checkbox("🐞 Enable Match Debugger", value=True)

if st.button("🚀 Run X-Ray Forecast"):
    
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        daily_lines_map = fetch_daily_text_lines()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7): week_map[today + timedelta(days=i)] = []
    valid_meetings = []
    
    # Sort by Name Length (Longest First) to prevent parents eating children
    all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            # --- THE LOGIC ---
            api_time = m.get("ScheduleTime")
            api_comments = m.get("Comments") or ""
            final_time = api_time
            
            # Debug Stats
            match_candidates = [] 
            
            # 1. Check API Comments
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            # 2. Scrape Match
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                if m_date in daily_lines_map:
                    lines = daily_lines_map[m_date]
                    api_tokens = get_clean_tokens(name)
                    
                    found_match_index = -1
                    best_overlap = 0
                    
                    # 2a. Find Best Header Line
                    for i, line_obj in enumerate(lines):
                        if line_obj['used']: continue 
                        
                        web_tokens = line_obj['tokens']
                        overlap = len(api_tokens.intersection(web_tokens))
                        
                        # Store for Debugger
                        if overlap > 0:
                            match_candidates.append({
                                "line": line_obj['text'], 
                                "score": overlap, 
                                "missing": list(api_tokens - web_tokens)
                            })
                        
                        # STRICT MATCH RULE: 
                        # Must match at least 70% of the API tokens OR contain ALL unique tokens
                        required_matches = max(1, len(api_tokens) - 1) # Allow 1 missing word
                        
                        if overlap >= required_matches and overlap > best_overlap:
                            best_overlap = overlap
                            found_match_index = i
                            
                    # 2b. Consume & Look Down
                    if found_match_index != -1:
                        # Mark consumed
                        lines[found_match_index]['used'] = True 
                        
                        # Look down 5 lines for time
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
            
            # Attach Debug Info
            if final_time == "Time TBA":
                m['DebugCandidates'] = sorted(match_candidates, key=lambda x: x['score'], reverse=True)[:3]
                m['ApiTokens'] = get_clean_tokens(name)
            
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
                        # TIME DISPLAY
                        if len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
                        else: st.markdown(f"**{time_str}**")
                        
                        # NAME DISPLAY
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        # DEBUGGER (Only if enabled + TBA)
                        if debug_mode and time_str == "Time TBA":
                            st.error("⚠️ MATCH FAILED")
                            st.write("API Tokens:", m.get('ApiTokens'))
                            if m.get('DebugCandidates'):
                                st.write("Best Candidates:")
                                for c in m['DebugCandidates']:
                                    st.code(f"Score: {c['score']} | {c['line']}")
                            else:
                                st.write("No similar lines found.")

                        # BILLS
                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
