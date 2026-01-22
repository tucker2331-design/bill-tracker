import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v43 LIS Master", page_icon="🏛️", layout="wide")
st.title("🏛️ v43: The 'LIS Master' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG TOGGLE ---
show_debug = st.sidebar.checkbox("Show Raw Scraper Table", value=True)
filter_text = st.sidebar.text_input("Filter Raw Table (e.g. 'Subcommittee #2')")

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    lower = text.lower()
    
    clean_text = lower.replace(".ics", "").replace("view agenda", "")
    clean_text = clean_text.replace("-", " ").replace("#", " ")
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    
    noise = {
        "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus",
        "general", "assembly", "commonwealth", "meeting"
    }
    return set(clean_text.split()) - noise

# --- COMPONENT 1: THE LIS SCRAPER (Source C - Dual Fetch) ---
@st.cache_data(ttl=300)
def fetch_lis_schedule():
    """
    Fetches raw LIS tables for BOTH House and Senate to match the user's 'All' view.
    Parses the exact table structure seen in the screenshot.
    """
    schedule_map = {} 
    raw_line_data = [] 
    
    # We fetch both chambers to ensure we cover the "Mixed" view
    urls = [
        ("House", "https://lis.virginia.gov/cgi-bin/legp604.exe?261+sbh+HOUS"),
        ("Senate", "https://lis.virginia.gov/cgi-bin/legp604.exe?261+sbh+SEN")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            raw_line_data.append({"date": "SYSTEM", "text": f"--- FETCHING {label} ---", "col1": "", "col2": ""})
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # LIS uses a main table. We look for rows.
            # The structure in your screenshot is:
            # Header Row: Date
            # Data Rows: [Time] [Committee Info]
            
            rows = soup.find_all('tr')
            current_date = None
            
            for row in rows:
                cells = row.find_all('td')
                if not cells: 
                    # Might be a Date Header in a <h4> inside a <ul> or outside the table
                    # LIS is messy. Let's check the text of the whole row.
                    row_text = row.get_text(" ", strip=True)
                    if any(day in row_text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                         # Date Detection
                        match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', row_text)
                        if match:
                            raw_str = f"{match.group(0)} 2026"
                            try: 
                                dt = datetime.strptime(raw_str, "%A, %B %d %Y")
                                current_date = dt.date()
                                raw_line_data.append({"date": str(current_date), "text": "DATE HEADER", "col1": "", "col2": ""})
                            except: pass
                    continue
                
                # If we have cells, it's likely a meeting
                # LIS rows usually have 2 or 3 columns.
                # Col 1: Time (e.g. "7:00 AM")
                # Col 2: Name (e.g. "House Counties...")
                
                if len(cells) >= 2:
                    time_text = cells[0].get_text(" ", strip=True)
                    info_text = cells[1].get_text(" ", strip=True)
                    
                    # Validate it's a meeting row
                    if not current_date: continue
                    if not info_text: continue
                    
                    # Store
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    
                    entry = {
                        "time_raw": time_text,
                        "name_raw": info_text,
                        "tokens": get_clean_tokens(info_text)
                    }
                    schedule_map[current_date].append(entry)
                    
                    # Debug log
                    raw_line_data.append({
                        "date": str(current_date), 
                        "text": "Meeting Row", 
                        "col1": time_text, 
                        "col2": info_text
                    })
                    
        except Exception as e:
            raw_line_data.append({"date": "ERROR", "text": str(e), "col1": "", "col2": ""})
            
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

# --- RESTORED BILL COUNTING LOGIC ---
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
    
with st.spinner("Scraping LIS Master Table..."):
    daily_lis_map, raw_debug_data = fetch_lis_schedule()

# --- THE OG DEV BOX ---
if show_debug:
    st.subheader("🔍 Raw LIS Table Output")
    st.info("Columns 1 & 2 match the screenshot structure: Time | Info")
    
    display_data = raw_debug_data
    if filter_text:
        display_data = [row for row in raw_debug_data if filter_text.lower() in str(row).lower()]
        
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
        
    # 2. LIS TABLE SEARCH
    elif m_date in daily_lis_map:
        lis_rows = daily_lis_map[m_date]
        api_tokens = get_clean_tokens(name)
        
        best_row = None
        best_score = 0.0
        
        for row in lis_rows:
            lis_tokens = row['tokens']
            intersection = api_tokens.intersection(lis_tokens)
            
            if not intersection: continue
            
            score = len(intersection) / len(api_tokens)
            if intersection.intersection({'1','2','3','4','5','6'}): score += 0.5
            
            # Boost for exact subcommittee match
            if "subcommittee" in name.lower() and "subcommittee" in row['name_raw'].lower():
                score += 0.2
            
            if score > best_score and score > 0.65:
                best_score = score
                best_row = row
        
        if best_row:
            # We trust LIS Time (Column 1) completely
            final_time = best_row['time_raw']
            if not final_time: final_time = "Time Not Listed"
    
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['CleanDate'] = m_date
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    valid_meetings.append(m)
    week_map[m_date].append(m)

# --- BILL SCANNING (RESTORED) ---
with st.spinner(f"🔥 Scanning bills for {len(valid_meetings)} agendas..."):
    bill_results = fetch_bills_parallel(valid_meetings)
    for m in valid_meetings: m['Bills'] = bill_results.get(m['ScheduleID'], [])

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
                    
                    if len(m.get('Bills', [])) > 0:
                        st.success(f"**{len(m['Bills'])} Bills Listed**")
                        with st.expander("View Bills"):
                            st.write(", ".join(m['Bills']))
                            
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
