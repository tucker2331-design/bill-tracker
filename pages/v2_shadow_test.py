import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v18 Final Polish", page_icon="💎", layout="wide")
st.title("💎 v18: Context-Aware Scheduler")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: NATURAL SORTING ---
def natural_sort_key(s):
    parts = re.match(r"([A-Za-z]+)(\d+)", s)
    if parts: return parts.group(1), int(parts.group(2))
    return s, 0

# --- HELPER: SMART TIME PARSER ---
def parse_time_rank(time_str):
    """
    Sorts meetings logically:
    1. Specific Times (8:00 AM) -> 0-899
    2. Floor Adjournment (After House/Senate) -> 900
    3. Committee Adjournment (After another comm) -> 910
    4. TBA -> 9999
    """
    if not time_str: return 9999
    
    clean = time_str.lower().replace(".", "").strip()
    
    # 1. HIERARCHY DETECTION
    if "adjourn" in clean or "recess" in clean:
        # If waiting for the whole House/Senate/Floor -> Priority 1 (3:00 PM equivalent)
        if any(x in clean for x in ["house", "senate", "floor", "session"]):
            return 900 
        # If waiting for another Committee -> Priority 2 (3:10 PM equivalent)
        else:
            return 910
            
    if "tba" in clean: return 9999
        
    # 2. STANDARD TIME PARSING
    try:
        dt = datetime.strptime(clean, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except:
        return 9999 # Fallback for weird text

# --- CORE FUNCTIONS ---
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
    seen_signatures = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_items.append(m)
    return unique_items

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text().lower()
        if any(x in text for x in ["agenda", "committee info", "docket"]):
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
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

def parse_committee_name(full_name):
    if " - " in full_name:
        parts = full_name.split(" - ", 1)
        return parts[0], parts[1]
    elif "Subcommittee" in full_name:
        return full_name, None
    return full_name, None

# --- MAIN UI ---

if st.button("🚀 Run Forecast"):
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7):
        week_map[today + timedelta(days=i)] = []
        
    valid_meetings = []
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            raw_time = m.get("ScheduleTime")
            raw_date_iso = m.get("ScheduleDate", "") 
            comments = m.get("Comments") or ""
            
            # --- THE LOGIC FIX ---
            # Priority 1: Use specific text instructions if available
            if "adjourn" in comments.lower() or "recess" in comments.lower():
                display_time = comments # <--- KEEP THE ORIGINAL TEXT
            # Priority 2: Use Time field
            elif raw_time:
                display_time = raw_time
            # Priority 3: Extract from Date ISO
            elif "T" in raw_date_iso:
                 try:
                    time_part = raw_date_iso.split("T")[1]
                    dt_obj = datetime.strptime(time_part, "%H:%M:%S")
                    if dt_obj.hour != 0 or dt_obj.minute != 0:
                        display_time = dt_obj.strftime("%-I:%M %p")
                    else:
                        display_time = "Time TBA"
                 except: display_time = "Time TBA"
            else:
                display_time = "Time TBA"
                
            m['FinalTime'] = display_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings:
        m['Bills'] = bill_results.get(m['ScheduleID'], [])

    cols = st.columns(7)
    days = sorted(week_map.keys())
    
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"### {day.strftime('%a')}")
            st.caption(day.strftime('%b %d'))
            st.divider()
            
            daily_meetings = week_map[day]
            
            # Sort: Fixed Times -> Floor Adj -> Comm Adj -> TBA
            daily_meetings.sort(key=lambda x: parse_time_rank(x.get("FinalTime")))
            
            if not daily_meetings:
                st.info("No Committees")
            else:
                for m in daily_meetings:
                    bill_count = len(m.get('Bills', []))
                    full_name = m.get("OwnerName", "")
                    parent_name, sub_name = parse_committee_name(full_name)
                    
                    time_str = m['FinalTime']
                    # Visual Cleanup: If text is huge, truncate it nicely or make it small
                    is_long_text = len(time_str) > 15
                    
                    with st.container(border=True):
                        # TIME DISPLAY
                        if is_long_text:
                            # Use italic caption for long instructions like "1/2 hr after..."
                            st.caption(f"🕒 *{time_str}*") 
                        else:
                            st.markdown(f"**{time_str}**")
                        
                        # NAME DISPLAY
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
