import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v30 Fuzzy Scorer", page_icon="🧮", layout="wide")
st.title("🧮 v30: The 'Fuzzy Score' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG TOGGLE ---
debug_mode = st.sidebar.checkbox("🐞 Match Debugger", value=True)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    # 1. Handle "Subcommittee #1" -> "subcommittee 1"
    clean_text = text.lower().replace("#", " ")
    clean_text = clean_text.replace("-", " ")
    # Keep alphanumeric (letters + numbers)
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus"
    }
    
    words = set(clean_text.split())
    # Return meaningful words + numbers
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
            # Detect Date
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    clean_date = line.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                    if current_date not in schedule_map: schedule_map[current_date] = []
                except: pass
            
            # Add Line
            if current_date:
                schedule_map[current_date].append({
                    "id": i,
                    "text": line,
                    "tokens": get_clean_tokens(line),
                    "used": False
                })
    except: pass
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

if st.button("🚀 Run Fuzzy Forecast"):
    
    with st.spinner("Fetching API..."):
        all_meetings = get_full_schedule()
        daily_lines_map = fetch_daily_text_lines()
        
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
            debug_info = []
            
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                if m_date in daily_lines_map:
                    lines = daily_lines_map[m_date]
                    api_tokens = get_clean_tokens(name)
                    
                    found_match_index = -1
                    best_score = 0.0
                    
                    for i, line_obj in enumerate(lines):
                        if line_obj['used']: continue
                        
                        web_tokens = line_obj['tokens']
                        if not web_tokens: continue
                        
                        # --- SCORING LOGIC ---
                        # Intersection / Union (Jaccard-ish)
                        intersection = api_tokens.intersection(web_tokens)
                        overlap_count = len(intersection)
                        
                        if overlap_count == 0: continue
                        
                        # Base Score: What % of API words were found?
                        score = overlap_count / len(api_tokens)
                        
                        # Bonus: Unique Numbers (1, 2, 3) are critical
                        numbers = {'1','2','3','4','5','6'}
                        common_numbers = intersection.intersection(numbers)
                        if common_numbers: score += 0.5 # Massive boost for matching "#2"
                        
                        debug_info.append(f"{score:.2f}: {line_obj['text']}")
                        
                        # Threshold: Match if > 50% score
                        if score > best_score and score > 0.5:
                            best_score = score
                            found_match_index = i
                            
                    if found_match_index != -1:
                        lines[found_match_index]['used'] = True
                        for offset in range(1, 6):
                            if found_match_index + offset >= len(lines): break
                            candidate = lines[found_match_index + offset]['text']
                            if is_time_string(candidate):
                                final_time = candidate
                                break
            
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
            
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            m['ApiTokens'] = get_clean_tokens(name)
            if final_time == "Time TBA": m['DebugInfo'] = sorted(debug_info, reverse=True)[:3]
            
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
                            st.error(f"MISSED: {m['ApiTokens']}")
                            for d in m.get('DebugInfo', []): st.caption(d)

                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
