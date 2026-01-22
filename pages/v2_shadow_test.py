import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v32 Calendar Inspector", page_icon="🕵️‍♀️", layout="wide")
st.title("🕵️‍♀️ v32: The Calendar Inspector")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    clean_text = text.lower().replace("#", " ").replace("-", " ")
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    noise = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus"
    }
    return set(clean_text.split()) - noise

def is_time_string(line):
    l = line.lower()
    if "adjourn" in l or "recess" in l or "upon" in l or "immediately" in l or "after" in l: return True
    if re.search(r'\d{1,2}:\d{2}', l) and ("am" in l or "pm" in l or "noon" in l): return True
    return False

# --- COMPONENT 1: THE FLAT SCRAPER ---
@st.cache_data(ttl=300)
def fetch_daily_text_lines():
    """
    Scrapes the website and organizes text into Date Buckets.
    """
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Get raw lines
        text_blob = soup.get_text("\n")
        raw_lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        current_date = "Unknown Date" # Default bucket for lost lines
        if current_date not in schedule_map: schedule_map[current_date] = []
        
        for i, line in enumerate(raw_lines):
            # 1. Detect Date Header
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    # Regex to extract standard date format
                    match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Z][a-z]+)\s+(\d{1,2})', line)
                    if match:
                        clean_date_str = f"{match.group(0)} 2026"
                        dt = datetime.strptime(clean_date_str, "%A, %B %d %Y")
                        current_date = dt.date()
                        if current_date not in schedule_map: schedule_map[current_date] = []
                except: pass
            
            # 2. Store Line
            if current_date:
                schedule_map[current_date].append({
                    "id": i,
                    "text": line,
                    "tokens": get_clean_tokens(line),
                    "used": False
                })
    except Exception as e: 
        st.error(f"Scraper Error: {e}")
        
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

# --- MATCHING ENGINE ---
def find_time_for_tokens(tokens, lines):
    found_match_index = -1
    best_score = 0.0
    debug_cands = []
    
    for i, line_obj in enumerate(lines):
        web_tokens = line_obj['tokens']
        if not web_tokens: continue
        
        intersection = tokens.intersection(web_tokens)
        overlap_count = len(intersection)
        if overlap_count == 0: continue
        
        # Scoring
        min_len = min(len(tokens), len(web_tokens))
        score = overlap_count / min_len if min_len > 0 else 0
        
        # Boost numbers
        if intersection.intersection({'1','2','3','4','5','6'}): score += 0.3
        
        if score > 0:
            debug_cands.append(f"{score:.2f} | {line_obj['text']}")
        
        if score > best_score and score > 0.6:
            best_score = score
            found_match_index = i
            
    if found_match_index != -1:
        # Look Down
        for offset in range(1, 6):
            if found_match_index + offset >= len(lines): break
            candidate = lines[found_match_index + offset]['text']
            if is_time_string(candidate):
                return candidate, debug_cands
    return None, debug_cands

# --- MAIN UI ---

# INSPECTOR CONTROLS
st.sidebar.header("🔍 Inspector Controls")
show_inspector = st.sidebar.checkbox("Show Calendar Inspector", value=True)
inspector_query = st.sidebar.text_input("Search Scraped Text (e.g. 'Capital Outlay')")

if st.button("🚀 Run Forecast & Inspect"):
    
    # 1. FETCH DATA
    with st.spinner("Fetching API..."):
        all_meetings = get_full_schedule()
        
    with st.spinner("Scraping Website (Source B)..."):
        daily_lines_map = fetch_daily_text_lines()

    # --- THE CALENDAR INSPECTOR UI ---
    if show_inspector:
        st.divider()
        st.subheader("🗓️ Calendar Inspector (Diagnostic)")
        
        # Metric: Dates Found
        found_dates = [d for d in daily_lines_map.keys() if isinstance(d, datetime) or isinstance(d, type(datetime.now().date()))]
        sorted_dates = sorted(found_dates)
        
        cols = st.columns(len(sorted_dates) + 1 if sorted_dates else 1)
        for i, d in enumerate(sorted_dates):
            count = len(daily_lines_map[d])
            cols[i].metric(d.strftime("%a %m/%d"), f"{count} Lines")
            
        if "Unknown Date" in daily_lines_map:
            cols[-1].metric("⚠️ Unknown Date", f"{len(daily_lines_map['Unknown Date'])} Lines", delta="Error", delta_color="inverse")

        # Search / Inspect
        with st.expander("🔎 Deep Dive: Raw Scraped Text", expanded=True):
            if inspector_query:
                st.info(f"Searching for: **'{inspector_query}'**")
                hits = []
                for d, lines in daily_lines_map.items():
                    d_str = d.strftime("%A %m/%d") if hasattr(d, 'strftime') else str(d)
                    for line_obj in lines:
                        if inspector_query.lower() in line_obj['text'].lower():
                            hits.append(f"**{d_str}**: {line_obj['text']}")
                
                if hits:
                    for h in hits: st.markdown(h)
                else:
                    st.warning("No text matches found in any date bucket.")
            else:
                # Show all text for first date as example
                if sorted_dates:
                    first_d = sorted_dates[0]
                    st.write(f"**Showing lines for {first_d.strftime('%A %m/%d')}:**")
                    st.dataframe([l['text'] for l in daily_lines_map[first_d]], use_container_width=True)

        st.divider()

    # --- NORMAL FORECAST RENDERING ---
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
            debug_log = []
            
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                if m_date in daily_lines_map:
                    lines = daily_lines_map[m_date]
                    api_tokens = get_clean_tokens(name)
                    
                    # Exact/Fuzzy Match
                    scraped_time, logs = find_time_for_tokens(api_tokens, lines)
                    debug_log = logs
                    
                    if scraped_time:
                        final_time = scraped_time
                    else:
                        # Parent Fallback
                        if "-" in name:
                            parent_name = name.split("-")[0].strip()
                            parent_tokens = get_clean_tokens(parent_name)
                            p_time, p_logs = find_time_for_tokens(parent_tokens, lines)
                            if p_time: final_time = f"See Parent: {p_time}"
            
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
            
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            m['ApiTokens'] = get_clean_tokens(name)
            if final_time == "Time TBA": m['DebugInfo'] = debug_log[:5]
            
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
                        
                        if time_str == "Time TBA":
                            st.error(f"MISSED")
                            if show_inspector:
                                with st.expander("Debug"):
                                    st.caption(f"Tokens: {m['ApiTokens']}")
                                    for l in m.get('DebugInfo', []): st.text(l)

                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
