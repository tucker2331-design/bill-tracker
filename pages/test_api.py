import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v86 Stable Merge", page_icon="📆", layout="wide")
st.title("📆 v86: Chronological Calendar (Stable + Fixed)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
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

# --- HELPER: COMPLEX TIME EXTRACTOR ---
def extract_complex_time(text):
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    
    if "cancel" in lower or "postpone" in lower: return "CANCELLED"

    keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "conclusion of",
        "commence", "convening", "15 minutes", "30 minutes",
        "1/2 hr", "half hour"
    ]
    if len(clean) < 150 and any(k in lower for k in keywords):
        return clean.strip()

    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    return None

def extract_agenda_link(description_html):
    if not description_html: return None
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

# --- NEW FEATURE: VISUAL SCHEDULE SCRAPER ---
def fetch_visual_schedule_lines(date_obj):
    """
    Fetches the text lines from the Daily Schedule page (dys).
    Used to correct times and catch cancellations.
    """
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        return [clean_html(line) for line in text.splitlines() if line.strip()]
    except: return []

# --- NEW FEATURE: BILL SCRAPER ---
def fetch_bills_from_agenda(url):
    """
    Scrapes the agenda page for bill numbers.
    """
    if not url: return []
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        pattern = r'\b([H|S][B|J|R]\s*\.?\s*\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        cleaned = sorted(list(set(m.upper().replace(" ", "").replace(".", "") for m in matches)))
        return cleaned
    except: return []

# --- API FETCH ---
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

# --- SORTING ---
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

with st.spinner("Syncing Official Schedule..."):
    all_raw_items = get_full_schedule()

# 1. PRE-PROCESS & IDENTIFY WORK
today = datetime.now().date()
tasks_bills = []
needed_days = set()
processed_events = []
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    # Deduplicate
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue # Skip past
    
    m['DateObj'] = d
    m['AgendaLink'] = extract_agenda_link(m.get("Description", ""))
    
    needed_days.add(d)
    if m['AgendaLink']:
        tasks_bills.append(m['AgendaLink'])
    
    processed_events.append(m)

# 2. PARALLEL FETCH (Visual Schedule + Bills)
visual_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        f_sched = {executor.submit(fetch_visual_schedule_lines, d): d for d in needed_days}
        f_bills = {executor.submit(fetch_bills_from_agenda, url): url for url in tasks_bills}
        
        for f in concurrent.futures.as_completed(f_sched):
            visual_cache[f_sched[f]] = f.result()
            
        for f in concurrent.futures.as_completed(f_bills):
            try: bill_cache[f_bills[f]] = f.result()
            except: pass

# 3. MERGE & REFINE
display_map = {}

for m in processed_events:
    name = m.get("OwnerName", "")
    api_time = m.get("ScheduleTime")
    d = m['DateObj']
    is_floor = "Convene" in name or "Session" in name
    
    # Start with API time
    final_time = api_time
    if not final_time:
        final_time = extract_complex_time(m.get("Comments"))
    if not final_time:
        final_time = extract_complex_time(m.get("Description"))
    
    source = "API"
    
    # --- VISUAL OVERRIDE (The Fix) ---
    # Check if the visual schedule has better info (Time or Cancellation)
    if d in visual_cache:
        lines = visual_cache[d]
        my_tokens = set(normalize_name(name).split())
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            
            # Fuzzy Match
            if my_tokens and my_tokens.issubset(line_tokens):
                # 1. Check Cancellation (Override API time if cancelled)
                prev_line = lines[i-1].lower() if i > 0 else ""
                if "cancel" in line_lower or "cancel" in prev_line:
                    final_time = "CANCELLED"
                    source = "Visual Schedule (Correction)"
                    break
                
                # 2. Check for Time (Fixes 12:00 PM Session)
                # Matches "12:00 PM House Convenes"
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    final_time = time_match.group(1).upper()
                    source = "Visual Schedule (Correction)"
                    break
                
                # 3. Check Relative Time
                if "adjourn" in line_lower or "upon" in line_lower or "adjourn" in prev_line:
                    final_time = "Upon Adjournment"
                    source = "Visual Schedule (Correction)"
                    break

    # Final Default
    if not final_time:
        if is_floor: final_time = "Time TBA"
        else: final_time = "Time Not Listed"

    m['DisplayTime'] = final_time
    m['IsFloor'] = is_floor
    m['Bills'] = bill_cache.get(m['AgendaLink'], [])
    m['Source'] = source
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found in API.")
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
                is_floor = event.get("IsFloor")
                bills = event.get("Bills")
                source = event.get("Source")
                
                is_cancelled = "CANCEL" in str(time_display).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                
                elif is_floor:
                    # FLOOR CARD
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        
                        if "TBA" in str(time_display):
                            st.warning("Time TBA")
                        else:
                            st.success(f"⏰ {time_display}")
                        
                        if agenda_link: st.link_button("View Calendar", agenda_link)
                
                else:
                    # COMMITTEE CARD
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

                        # BILL LIST
                        if bills:
                            with st.expander(f"📜 {len(bills)} Bills"):
                                st.write(", ".join(bills))
                                if agenda_link:
                                    st.link_button("Full Agenda", agenda_link)
                        elif agenda_link:
                            st.link_button("Agenda", agenda_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        # Transparency Footer
                        if source != "API":
                            st.caption(f"ℹ️ Updated via {source}")
                        
                        st.divider()
