import streamlit as st
import requests
import re
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v92 Docket Hunter", page_icon="🏛️", layout="wide")
st.title("🏛️ v92: The 'Docket Hunter'")

# --- DEBUG MODE (Sidebar) ---
# Check this box to see exactly what URLs the scraper is finding
debug_mode = st.sidebar.checkbox("🐞 Enable Debug Mode", value=False)

# --- NETWORK ENGINE (SAFE) ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Connection': 'keep-alive'
}

# --- HELPER FUNCTIONS ---
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

# --- THE FIX: SMART LINK EXTRACTOR ---
def extract_best_link(description_html):
    """
    Scans description HTML for multiple links and picks the best one.
    Priority: Docket/Agenda > Bill List > Committee Info
    """
    if not description_html: return None
    
    soup = BeautifulSoup(description_html, 'html.parser')
    best_link = None
    best_score = 0
    
    for a in soup.find_all('a'):
        href = a.get('href', '')
        text = a.get_text().lower()
        
        # Normalize relative URLs
        if href.startswith("/"): 
            href = f"https://house.vga.virginia.gov{href}"
        
        # Scoring Logic
        score = 0
        if "docket" in text or "docket" in href.lower(): score = 10 # Highest Priority
        elif "agenda" in text or "agenda" in href.lower(): score = 9
        elif "bill" in text or "list" in text: score = 5
        elif "committee info" in text: score = 1 # Fallback
        
        if score > best_score:
            best_score = score
            best_link = href
            
    return best_link

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

# --- SCRAPERS ---
def fetch_visual_schedule_lines(date_obj):
    time.sleep(random.uniform(0.1, 0.3))
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        return [clean_html(line) for line in text.splitlines() if line.strip()]
    except: return []

def scan_agenda_page(url):
    time.sleep(random.uniform(0.1, 0.3))
    if not url: return []
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for bills (matches HB100, S.B. 50, etc.)
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        
        clean = set()
        for p, n in bills:
            clean.add(f"{p.upper().replace('.','').strip()}{n}")
            
        def n_sort(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
            
        return sorted(list(clean), key=n_sort)
    except: return []

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: # Safety limit
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: raw_items.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw_items.extend(s.result().json().get("Schedules", []))
            return raw_items
    except: return []

# --- MAIN LOGIC ---

with st.spinner("Initializing..."):
    all_raw_items = get_full_schedule()

today = datetime.now().date()
tasks_bills = []
needed_days = set()
processed_events = []
seen_sigs = set()

# 1. PRE-PROCESS
for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = d
    # Use the new SMART link extractor
    m['AgendaLink'] = extract_best_link(m.get("Description", ""))
    
    needed_days.add(d)
    if m['AgendaLink']:
        tasks_bills.append(m['AgendaLink'])
    
    processed_events.append(m)

# 2. PARALLEL EXECUTION
schedule_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    with st.spinner(f"Reading {len(tasks_bills)} Dockets/Agendas..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            f_sched = {executor.submit(fetch_visual_schedule_lines, d): d for d in needed_days}
            f_bills = {executor.submit(scan_agenda_page, url): url for url in tasks_bills}
            
            for f in concurrent.futures.as_completed(f_sched):
                try: schedule_cache[f_sched[f]] = f.result()
                except: pass
            
            for f in concurrent.futures.as_completed(f_bills):
                try: bill_cache[f_bills[f]] = f.result()
                except: pass

# 3. MERGE & DISPLAY
display_map = {}

for m in processed_events:
    name = m.get("OwnerName", "")
    api_time = m.get("ScheduleTime")
    d = m['DateObj']
    
    final_time = api_time
    source_label = "API"
    
    # Visual Override Logic (Same as v82/v91)
    if d in schedule_cache:
        lines = schedule_cache[d]
        my_tokens = set(normalize_name(name).split())
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            if my_tokens and my_tokens.issubset(line_tokens):
                prev_line = lines[i-1].lower() if i > 0 else ""
                if "cancel" in line_lower or "cancel" in prev_line:
                    final_time = "CANCELLED"
                    source_label = "Sched"
                    break
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    final_time = time_match.group(1).upper()
                    source_label = "Sched"
                    break
                if "adjourn" in line_lower or "upon" in line_lower:
                    final_time = "Upon Adjournment"
                    source_label = "Sched"
                    break

    if not final_time:
        if "Convene" in name: final_time = "Time TBA"
        else: final_time = "Time Not Listed"

    m['DisplayTime'] = final_time
    m['Bills'] = bill_cache.get(m['AgendaLink'], [])
    m['Source'] = source_label
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER ---
if not display_map:
    st.info("No upcoming events found.")
else:
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
                        # Time
                        if "TBA" in str(time_display) or "Not Listed" in str(time_display):
                            st.caption(f"⚠️ {time_display}")
                        elif len(str(time_display)) > 15:
                            st.markdown(f"**{time_display}**")
                        else:
                            st.markdown(f"**⏰ {time_display}**")
                        
                        # Name
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        # Bills / Link
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View List"):
                                st.write(", ".join(bills))
                                if agenda_link: st.link_button("View Docket/Agenda", agenda_link)
                        elif agenda_link:
                            # Decide button text based on link content
                            btn_text = "View Docket" if "docket" in agenda_link.lower() else "View Agenda"
                            st.link_button(btn_text, agenda_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        # DEBUGGER
                        if debug_mode:
                            st.divider()
                            st.caption(f"🔗 Found: {agenda_link}")
                            st.caption(f"ℹ️ Source: {event['Source']}")
