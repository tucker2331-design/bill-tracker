import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v42 Hybrid Restoration", page_icon="⚖️", layout="wide")
st.title("⚖️ v42: The 'Hybrid' (Restored Data + Speed Toggle)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- SIDEBAR CONTROLS ---
st.sidebar.header("⚙️ Configuration")
enable_deep_scan = st.sidebar.checkbox("Enable Deep Bill Scan (Slower)", value=False, help="Checks every agenda page to count bills. Turn off for speed.")
show_debug = st.sidebar.checkbox("Show Raw Scraper Table", value=False)
filter_text = st.sidebar.text_input("Filter Raw Table (e.g. 'Jan 26')")

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    lower = text.lower()
    is_session = "convenes" in lower or "session" in lower
    
    clean_text = lower.replace(".ics", "").replace("view agenda", "")
    clean_text = clean_text.replace("-", " ").replace("#", " ")
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    noise = {
        "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus",
        "general", "assembly", "commonwealth", "meeting"
    }
    
    if not is_session:
        noise.update({"house", "senate"})
        
    return set(clean_text.split()) - noise

def extract_time_from_block(block_text):
    lower_text = block_text.lower()
    if "cancel" in lower_text: return "❌ Cancelled"
    if "noon" in lower_text: return "12:00 PM"

    if "adjourn" in lower_text or "recess" in lower_text:
        for line in block_text.splitlines():
            if "adjourn" in line.lower() or "recess" in line.lower():
                return line.strip()

    time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', block_text)
    if time_match: return time_match.group(1).upper()
    return None

# --- COMPONENT 1: THE HOUSE SCRAPER (Source B - Restored) ---
@st.cache_data(ttl=300)
def fetch_scraper_data():
    """
    Fetches house.vga.virginia.gov for CURRENT and NEXT week.
    """
    schedule_map = {} 
    raw_line_data = [] 
    
    # Calculate Next Monday
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() if today.weekday() > 0 else 0 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    next_monday_str = next_monday.strftime("%Y-%m-%d")
    
    # We guess the URL pattern for next week
    urls = [
        ("Current Week", "https://house.vga.virginia.gov/schedule/meetings"),
        ("Next Week", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday_str}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            raw_line_data.append({"date": "SYSTEM", "text": f"--- FETCHING {label}: {url} ---", "tag": "info"})
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Grab all text containers
            all_tags = soup.find_all(['div', 'span', 'p', 'h4', 'h5', 'a', 'li'])
            
            current_date = None
            current_block_lines = []
            
            for tag in all_tags:
                text = tag.get_text(" ", strip=True)
                if not text: continue
                
                # DATE DETECTION
                # Captures "Monday, January 26" OR "Monday, Jan 26"
                if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                    match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                    if match:
                        if current_date and current_block_lines:
                            if current_date not in schedule_map: schedule_map[current_date] = []
                            schedule_map[current_date].append("\n".join(current_block_lines))
                            current_block_lines = []
                        
                        raw_str = f"{match.group(0)} 2026"
                        try: dt = datetime.strptime(raw_str, "%A, %B %d %Y")
                        except: 
                            try: dt = datetime.strptime(raw_str, "%A, %b %d %Y")
                            except: continue

                        current_date = dt.date()
                        raw_line_data.append({"date": str(current_date), "text": f"DATE FOUND: {text}", "tag": "HEADER"})
                        continue
                
                raw_line_data.append({"date": str(current_date) if current_date else "Unknown", "text": text, "tag": tag.name})

                if not current_date: continue
                
                # BLOCK LOGIC
                is_new_start = "convenes" in text.lower()
                if is_new_start and current_block_lines:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append("\n".join(current_block_lines))
                    current_block_lines = []

                current_block_lines.append(text)
                
                low_text = text.lower()
                if ".ics" in low_text or "archived" in low_text or "pledge" in low_text:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append("\n".join(current_block_lines))
                    current_block_lines = []
                    
            if current_date and current_block_lines:
                if current_date not in schedule_map: schedule_map[current_date] = []
                schedule_map[current_date].append("\n".join(current_block_lines))
                
        except Exception as e: 
            raw_line_data.append({"date": "ERROR", "text": f"Failed {label}: {e}", "tag": "error"})
            
    return schedule_map, raw_line_data

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

# 1. FETCH DATA
with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()
    daily_blocks_map, raw_debug_data = fetch_scraper_data()

# --- THE OG DEV BOX ---
if show_debug:
    st.subheader("🔍 Raw Scraper Output (Multi-Week)")
    display_data = raw_debug_data
    if filter_text:
        display_data = [row for row in raw_debug_data if filter_text.lower() in row['text'].lower()]
    st.dataframe(display_data, use_container_width=True, height=400)
    st.divider()

# --- FORECAST LOGIC ---
today = datetime.now().date()
week_map = {}
for i in range(14): 
    week_map[today + timedelta(days=i)] = []
    
valid_meetings = []
all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: week_map[m_date] = []
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    final_time = "⚠️ Not Listed on Schedule"
    match_debug = []
    
    # 1. API Comments
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
            
            score = len(intersection) / len(api_tokens)
            if intersection.intersection({'1','2','3','4','5','6'}): score += 0.5
            
            if "convenes" in name.lower() and "convenes" in block_text.lower():
                score += 2.0 
            
            if score > best_score and score > 0.65:
                best_score = score
                best_block = block_text
        
        if best_block:
            extracted_time = extract_time_from_block(best_block)
            if extracted_time: final_time = extracted_time
            else: final_time = "Time Not Listed"
    
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['CleanDate'] = m_date
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    valid_meetings.append(m)
    week_map[m_date].append(m)

# --- BILL SCANNING (CONDITIONAL) ---
if enable_deep_scan:
    with st.spinner(f"🔥 Scanning bills (Slower)..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        for m in valid_meetings: m['Bills'] = bill_results.get(m['ScheduleID'], [])
else:
    for m in valid_meetings: m['Bills'] = []

# --- DISPLAY ---
cols = st.columns(7)
days = sorted([d for d in week_map.keys() if d <= today + timedelta(days=6)])

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
                    
                    # BILLS
                    if enable_deep_scan and len(m.get('Bills', [])) > 0:
                        st.success(f"**{len(m['Bills'])} Bills Listed**")
                        with st.expander("View Bills"):
                            st.write(", ".join(m['Bills']))
                            
                    # LINK
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
