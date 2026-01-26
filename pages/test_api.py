import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v91 Best of Both", page_icon="🏛️", layout="wide")
st.title("🏛️ v91: Schedule Truth + Bill Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("&nbsp;", " ").replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def normalize_name(name):
    if not name: return ""
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&"]:
        clean = clean.replace(word, "")
    return " ".join(clean.split())

# --- COMPONENT 1: VISUAL SCHEDULE SCRAPER (The Time/Status Fix) ---
@st.cache_data(ttl=300)
def fetch_visual_schedule_lines(date_obj):
    """
    Fetches the 'dys' text lines. Matches the user's screenshot source.
    """
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        return [clean_html(line) for line in text.splitlines() if line.strip()]
    except: return []

# --- COMPONENT 2: BILL SCRAPER (From v30) ---
@st.cache_data(ttl=600)
def scan_agenda_page(url):
    """
    Uses v30 Regex logic to find bills in the agenda.
    """
    if not url: return []
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        
        # v30 Regex Pattern
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        
        clean = set()
        for p, n in bills:
            # Normalize HB 100 -> HB100
            clean.add(f"{p.upper().replace('.','').strip()}{n}")
            
        def n_sort(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
            
        return sorted(list(clean), key=n_sort)
    except: return []

# --- API FETCH (CORE) ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: raw_items.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw_items.extend(s.result().json().get("Schedules", []))
            
        return raw_items
    except: return []

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if any(x in link.get_text().lower() for x in ["agenda", "committee info", "docket"]):
            return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    if "TBA" in t_upper: return 9999
    if "ADJOURN" in t_upper or "UPON" in t_upper: return 2000 
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- MAIN APP LOGIC ---

with st.spinner("Syncing Schedule & Scanning Bills..."):
    all_raw_items = get_full_schedule()

# 1. PRE-PROCESS & IDENTIFY TASKS
today = datetime.now().date()
tasks_bills = []
needed_days = set()
processed_events = []
seen_sigs = set()

# Optimization: Only look at future events
future_raw = []
for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if raw_date:
        d = datetime.strptime(raw_date, "%Y-%m-%d").date()
        if d >= today:
            future_raw.append((d, m))

for d, m in future_raw:
    sig = (m.get("ScheduleDate"), m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = d
    m['AgendaLink'] = extract_agenda_link(m.get("Description", ""))
    
    needed_days.add(d)
    if m['AgendaLink']:
        tasks_bills.append(m['AgendaLink'])
    
    processed_events.append(m)

# 2. PARALLEL EXECUTION (Schedule + Bills)
schedule_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    # We use 10 workers to be safe but fast
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Task A: Fetch Visual Schedules (Time Truth)
        f_sched = {executor.submit(fetch_visual_schedule_lines, d): d for d in needed_days}
        # Task B: Fetch Bills (Content Truth)
        f_bills = {executor.submit(scan_agenda_page, url): url for url in tasks_bills}
        
        for f in concurrent.futures.as_completed(f_sched):
            schedule_cache[f_sched[f]] = f.result()
            
        for f in concurrent.futures.as_completed(f_bills):
            try: bill_cache[f_bills[f]] = f.result()
            except: pass

# 3. MERGE LOGIC
display_map = {}

for m in processed_events:
    name = m.get("OwnerName", "")
    api_time = m.get("ScheduleTime")
    d = m['DateObj']
    
    final_time = api_time
    source_label = "API"
    
    # --- VISUAL OVERRIDE (Fixes Times & Cancellations) ---
    if d in schedule_cache:
        lines = schedule_cache[d]
        my_tokens = set(normalize_name(name).split())
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            
            # Fuzzy Match
            if my_tokens and my_tokens.issubset(line_tokens):
                prev_line = lines[i-1].lower() if i > 0 else ""
                
                # Check Cancellation
                if "cancel" in line_lower or "cancel" in prev_line:
                    final_time = "CANCELLED"
                    source_label = "Visual Sched"
                    break
                
                # Check Time (e.g. 12:00 PM)
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    final_time = time_match.group(1).upper()
                    source_label = "Visual Sched"
                    break
                
                # Check Relative
                if "adjourn" in line_lower or "upon" in line_lower:
                    final_time = "Upon Adjournment"
                    source_label = "Visual Sched"
                    break

    # Fallback Defaults
    if not final_time:
        if "Convene" in name: final_time = "Time TBA"
        else: final_time = "Time Not Listed"

    m['DisplayTime'] = final_time
    m['Bills'] = bill_cache.get(m['AgendaLink'], [])
    m['Source'] = source_label
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found.")
else:
    # Sort dates and limit to next 7 days for cleanliness
    sorted_dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            for event in day_events:
                name = event.get("OwnerName").replace("Virginia ", "").replace(" of Delegates", "")
                time_display = event.get("DisplayTime")
                agenda_link = event.get("AgendaLink")
                bills = event.get("Bills", [])
                
                is_cancelled = "CANCEL" in str(time_display).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                
                else:
                    with st.container(border=True):
                        # TIME HEADER
                        if "TBA" in str(time_display) or "Not Listed" in str(time_display):
                            st.caption(f"⚠️ {time_display}")
                        elif len(str(time_display)) > 15:
                            st.markdown(f"**{time_display}**")
                        else:
                            st.markdown(f"**⏰ {time_display}**")
                        
                        # NAME
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        # BILL DISPLAY (v30 Style)
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(bills))
                                if agenda_link:
                                    st.link_button("Full Agenda", agenda_link)
                        elif agenda_link:
                            st.link_button("Agenda", agenda_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        # Debug Footer (Optional)
                        # st.caption(f"Src: {event['Source']}")
