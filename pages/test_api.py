import streamlit as st
import requests
import re
import time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v88 Safe-Load", page_icon="🛡️", layout="wide")
st.title("🛡️ v88: Safe-Load Calendar (Crash-Proof)")

# --- NETWORK ENGINE (SAFE MODE) ---
session = requests.Session()
# CRITICAL FIX: Limit connection pool to prevent "Too many open files"
adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5)
session.mount('https://', adapter)

# Headers to look like a real browser (Anti-Ban)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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

def extract_agenda_link(description_html):
    if not description_html: return None
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

def extract_complex_time(text):
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    if "cancel" in lower: return "CANCELLED"
    keywords = ["adjournment", "adjourn", "upon", "immediate", "rise of", "recess", "after the"]
    if len(clean) < 150 and any(k in lower for k in keywords):
        return clean.strip()
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
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

# --- SCRAPERS (THROTTLED) ---
def fetch_visual_schedule_lines(date_obj):
    # Add delay to prevent rate limiting
    time.sleep(0.1) 
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        return [clean_html(line) for line in text.splitlines() if line.strip()]
    except: return []

def fetch_bills_from_agenda(url):
    time.sleep(0.1)
    if not url: return []
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        pattern = r'\b([H|S][B|J|R]\s*\.?\s*\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        cleaned = sorted(list(set(m.upper().replace(" ", "").replace(".", "") for m in matches)))
        return cleaned
    except: return []

# --- API FETCH (CORE) ---
@st.cache_data(ttl=600) 
def get_basic_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        # Sequential fetch is safer for startup
        h = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
        s = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
        
        raw_items = []
        if h.status_code == 200: raw_items.extend(h.json().get("Schedules", []))
        if s.status_code == 200: raw_items.extend(s.json().get("Schedules", []))
        return raw_items
    except: return []

# --- MAIN LOGIC ---

# 1. Load Basic Data (Instant)
if 'enhanced_data' not in st.session_state:
    st.session_state.enhanced_data = {}

all_raw_items = get_basic_schedule()

today = datetime.now().date()
display_map = {}
future_items = []
seen_sigs = set()

# Pre-process basic API data
for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)
    
    m['DateObj'] = d
    m['AgendaLink'] = extract_agenda_link(m.get("Description", ""))
    
    # Default Time Logic
    api_time = m.get("ScheduleTime")
    final_time = api_time
    if not final_time: final_time = extract_complex_time(m.get("Comments"))
    if not final_time: final_time = extract_complex_time(m.get("Description"))
    
    # Placeholder Logic
    if not final_time:
        if "Convene" in m.get("OwnerName", ""): final_time = "Time TBA"
        else: final_time = "Time Not Listed"
            
    m['DisplayTime'] = final_time
    m['Bills'] = []
    m['Source'] = "API"
    
    future_items.append(m)

# 2. Render Control Panel
col1, col2 = st.columns([3, 1])
with col1:
    st.info(f"Loaded {len(future_items)} upcoming events. Click Sync to check cancellations & bills.")
with col2:
    # THE SAFETY BUTTON
    if st.button("🔄 Sync Status & Bills", type="primary"):
        with st.status("Scanning LIS (Low & Slow Mode)...", expanded=True) as status:
            
            # Identify work for the next 7 days ONLY
            target_days = sorted(list(set(item['DateObj'] for item in future_items)))[:7]
            target_links = [item['AgendaLink'] for item in future_items if item['AgendaLink'] and item['DateObj'] in target_days]
            
            # MAX_WORKERS = 4 (Very Safe)
            
            st.write("Verifying Schedule...")
            sched_cache = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                f_sched = {executor.submit(fetch_visual_schedule_lines, d): d for d in target_days}
                for f in concurrent.futures.as_completed(f_sched):
                    sched_cache[f_sched[f]] = f.result()
            
            st.write(f"Reading {len(target_links)} Agendas...")
            bill_cache = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                f_bills = {executor.submit(fetch_bills_from_agenda, url): url for url in target_links}
                for f in concurrent.futures.as_completed(f_bills):
                    try: bill_cache[f_bills[f]] = f.result()
                    except: pass
            
            # Store in Session State
            st.session_state.enhanced_data = {
                'sched': sched_cache,
                'bills': bill_cache
            }
            status.update(label="Sync Complete!", state="complete", expanded=False)

# 3. Apply Enhancements (If Available)
sched_cache = st.session_state.enhanced_data.get('sched', {})
bill_cache = st.session_state.enhanced_data.get('bills', {})

for m in future_items:
    d = m['DateObj']
    name = m['OwnerName']
    
    # Bill Overlay
    if m['AgendaLink'] in bill_cache:
        m['Bills'] = bill_cache[m['AgendaLink']]
    
    # Schedule Overlay (Time Correction)
    if d in sched_cache:
        lines = sched_cache[d]
        my_tokens = set(normalize_name(name).split())
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            
            if my_tokens and my_tokens.issubset(line_tokens):
                # Check Cancellation
                prev_line = lines[i-1].lower() if i > 0 else ""
                if "cancel" in line_lower or "cancel" in prev_line:
                    m['DisplayTime'] = "❌ CANCELLED"
                    m['Source'] = "Visual Schedule"
                    break
                
                # Check Time
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    m['DisplayTime'] = time_match.group(1).upper()
                    m['Source'] = "Visual Schedule"
                    break
                
                # Check Relative
                if "adjourn" in line_lower or "upon" in line_lower:
                    m['DisplayTime'] = "Upon Adjournment"
                    m['Source'] = "Visual Schedule"
                    break

    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# 4. Render UI
if not display_map:
    st.warning("No events found.")
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
                bills = event.get("Bills")
                source = event.get("Source")
                
                is_cancelled = "CANCEL" in str(time_display).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                
                else:
                    if "Convene" in name:
                        with st.container(border=True):
                            st.markdown(f"**🏛️ {name}**")
                            if "TBA" in str(time_display): st.warning("Time TBA")
                            else: st.success(f"⏰ {time_display}")
                            if agenda_link: st.link_button("Calendar", agenda_link)
                    else:
                        with st.container():
                            if "TBA" in str(time_display) or "Not Listed" in str(time_display):
                                st.caption(f"⚠️ {time_display}")
                            elif len(str(time_display)) > 15:
                                st.markdown(f"**{time_display}**")
                            else:
                                st.markdown(f"**⏰ {time_display}**")
                            
                            clean_name = name.replace("Committee", "").strip()
                            st.markdown(f"{clean_name}")
                            if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                            if bills:
                                with st.expander(f"📜 {len(bills)} Bills"):
                                    st.write(", ".join(bills))
                                    if agenda_link: st.link_button("Full Agenda", agenda_link)
                            elif agenda_link:
                                st.link_button("Agenda", agenda_link)
                            else:
                                st.caption("*(No Link)*")
                            
                            if source != "API": st.caption(f"ℹ️ {source}")
                            st.divider()
