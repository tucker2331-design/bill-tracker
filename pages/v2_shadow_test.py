import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v29 Structure Scraper", page_icon="🏗️", layout="wide")
st.title("🏗️ v29: The HTML Structure Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG TOGGLE ---
debug_mode = st.sidebar.checkbox("🐞 Match Debugger", value=True)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    clean_text = text.replace("-", " ").lower()
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus"
    }
    words = set(clean_text.split())
    return words - noise

def is_time_string(text):
    l = text.lower()
    if "adjourn" in l or "recess" in l or "upon" in l or "immediately" in l or "after" in l: return True
    if re.search(r'\d{1,2}:\d{2}', l) and ("am" in l or "pm" in l or "noon" in l): return True
    return False

# --- COMPONENT 1: THE STRUCTURE SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_daily_structure():
    """
    Returns a map: { DateObject: [ {tokens: set, time_text: str} ] }
    This version walks the HTML TREE instead of reading lines.
    """
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # KEY INSIGHT: The schedule is likely a list of Headers (h4/div) followed by Details
        # We find all "Blocks" that look like committee headers
        
        # 1. Find all potential Committee Headers
        # Based on your screenshots, these are often links <a> or bold <strong> tags inside divs
        # We grab essentially EVERYTHING and filter later.
        all_elements = soup.find_all(['div', 'span', 'p', 'h4', 'h5', 'a'])
        
        current_date = None
        
        for i, elem in enumerate(all_elements):
            text = elem.get_text(" ", strip=True)
            if not text: continue
            
            # A. DATE DETECTOR
            if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2})', text)
                    if match:
                        clean_date = f"{match.group(0)} 2026"
                        dt = datetime.strptime(clean_date, "%A, %B %d %Y")
                        current_date = dt.date()
                        if current_date not in schedule_map: schedule_map[current_date] = []
                except: pass
                continue # It's a date header, move on
            
            # B. COMMITTEE BLOCK DETECTOR
            # If we are inside a date, and this looks like a committee name...
            if current_date and len(text) > 10 and len(text) < 100:
                # Basic check: does it have committee-like words?
                if "committee" in text.lower() or "caucus" in text.lower() or "commission" in text.lower():
                    
                    # FOUND A HEADER: Now look at its immediate neighbors in the list
                    # We look forward up to 10 elements to find the time
                    found_time = None
                    
                    for offset in range(1, 10):
                        if i + offset >= len(all_elements): break
                        
                        sibling = all_elements[i + offset]
                        sib_text = sibling.get_text(" ", strip=True)
                        
                        # Stop if we hit another Header/Date
                        if "committee" in sib_text.lower() and len(sib_text) < 100: break 
                        if "Monday," in sib_text or "Tuesday," in sib_text: break
                        
                        # Check for Time
                        if is_time_string(sib_text):
                            found_time = sib_text
                            break # Found it!
                    
                    if found_time:
                        schedule_map[current_date].append({
                            "tokens": get_clean_tokens(text),
                            "raw_name": text,
                            "time_text": found_time
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

if st.button("🚀 Run Structure Forecast"):
    
    with st.spinner("Fetching API..."):
        all_meetings = get_full_schedule()
        
    with st.spinner("Walking HTML Tree..."):
        daily_structure_map = fetch_daily_structure()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7): week_map[today + timedelta(days=i)] = []
    valid_meetings = []
    
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
            final_time = api_time
            debug_cands = []
            
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                if m_date in daily_structure_map:
                    scraped_blocks = daily_structure_map[m_date]
                    api_tokens = get_clean_tokens(name)
                    
                    best_overlap = 0
                    
                    for block in scraped_blocks:
                        web_tokens = block['tokens']
                        overlap = len(api_tokens.intersection(web_tokens))
                        
                        debug_cands.append(f"{overlap}: {block['raw_name']}")
                        
                        # Match: Needs Significant Overlap
                        if overlap > 0 and overlap >= max(1, len(api_tokens) - 1) and overlap > best_overlap:
                            best_overlap = overlap
                            final_time = block['time_text']
            
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
            
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            m['ApiTokens'] = get_clean_tokens(name)
            if final_time == "Time TBA": m['DebugCandidates'] = debug_cands[:5]
            
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
                        if len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
                        else: st.markdown(f"**{time_str}**")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        if debug_mode and time_str == "Time TBA":
                            st.error("MISSED")
                            st.write(m['ApiTokens'])
                            if m.get('DebugCandidates'):
                                for c in m['DebugCandidates']: st.text(c)

                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
