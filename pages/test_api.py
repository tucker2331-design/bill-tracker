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
st.title("📆 v86: The 'Stable Merge' (Working Base + Bills + Session)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def normalize_name(name):
    if not name: return ""
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&"]:
        clean = clean.replace(word, "")
    return " ".join(clean.split())

# --- FEATURE 1: BILL SCRAPER ---
def fetch_bills_from_agenda(url):
    """
    Scrapes the agenda page for bill numbers (HB1234, SB50).
    """
    if not url: return []
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        # Regex for bills (e.g. HB 1234, S.B. 50, HJ 100)
        pattern = r'\b([H|S][B|J|R]\s*\.?\s*\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        # Deduplicate and clean
        cleaned = sorted(list(set(m.upper().replace(" ", "").replace(".", "") for m in matches)))
        return cleaned
    except: return []

# --- FEATURE 2: VISUAL SCHEDULE (For Accurate Times/Status) ---
def fetch_visual_schedule_lines(date_obj):
    """
    Fetches the text lines from the Daily Schedule page (dys).
    """
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        return [clean_html(line) for line in text.splitlines() if line.strip()]
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

with st.spinner("Syncing Schedule & Bills..."):
    all_raw_items = get_full_schedule()

# 1. Identify Work
today = datetime.now().date()
tasks_bills = []
needed_days = set()

# Pre-filter for future events only (Optimization)
future_items = []
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue # Skip past events
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)
    
    m['DateObj'] = d
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    # Track what we need to fetch
    needed_days.add(d)
    if m['AgendaLink']:
        tasks_bills.append(m['AgendaLink'])
    
    future_items.append(m)

# 2. Parallel Fetch (Bills + Visual Schedule)
schedule_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
        # Fetch Visual Schedules (Time/Status Truth)
        f_sched = {executor.submit(fetch_visual_schedule_lines, d): d for d in needed_days}
        # Fetch Bills (Content)
        f_bills = {executor.submit(fetch_bills_from_agenda, url): url for url in tasks_bills}
        
        for f in concurrent.futures.as_completed(f_sched):
            schedule_cache[f_sched[f]] = f.result()
            
        for f in concurrent.futures.as_completed(f_bills):
            try: bill_cache[f_bills[f]] = f.result()
            except: pass

# 3. Process & Merge
display_map = {}

for m in future_items:
    name = m.get("OwnerName", "")
    api_time = m.get("ScheduleTime")
    d = m['DateObj']
    
    final_time = api_time
    
    # --- MERGE LOGIC: Check Visual Schedule ---
    # We use this to fix "TBA" times and catch "CANCELLED"
    if d in schedule_cache:
        lines = schedule_cache[d]
        my_tokens = set(normalize_name(name).split())
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            
            # Fuzzy Match
            if my_tokens and my_tokens.issubset(line_tokens):
                # 1. Check Cancellation
                prev_line = lines[i-1].lower() if i > 0 else ""
                if "cancel" in line_lower or "cancel" in prev_line:
                    final_time = "❌ CANCELLED"
                    break
                
                # 2. Check Time (Fixes 12:00 PM Session)
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    final_time = time_match.group(1).upper()
                    break
                
                # 3. Check "Upon Adjournment"
                if "adjourn" in line_lower or "upon" in line_lower:
                    final_time = "Upon Adjournment"
                    break

    # Final Fallback
    if not final_time:
        if "Convene" in name: final_time = "Time TBA"
        else: final_time = "Time Not Listed"

    m['DisplayTime'] = final_time
    m['Bills'] = bill_cache.get(m['AgendaLink'], [])
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER UI ---
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
                    # Determine Card Style
                    if "Convene" in name:
                        # Floor Session Card
                        with st.container(border=True):
                            st.markdown(f"**🏛️ {name}**")
                            if "TBA" in str(time_display): st.warning("Time TBA")
                            else: st.success(f"⏰ {time_display}")
                            
                            if agenda_link: st.link_button("Calendar", agenda_link)
                            
                    else:
                        # Committee Card
                        with st.container():
                            # Time Formatting
                            if "TBA" in str(time_display) or "Not Listed" in str(time_display):
                                st.caption(f"⚠️ {time_display}")
                            elif len(str(time_display)) > 15:
                                st.markdown(f"**{time_display}**")
                            else:
                                st.markdown(f"**⏰ {time_display}**")
                            
                            # Name Formatting
                            clean_name = name.replace("Committee", "").strip()
                            st.markdown(f"{clean_name}")
                            if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                            # BILLS EXPANDER (The New Feature)
                            if bills:
                                with st.expander(f"📜 {len(bills)} Bills"):
                                    st.write(", ".join(bills))
                                    if agenda_link:
                                        st.link_button("Full Agenda", agenda_link)
                            elif agenda_link:
                                st.link_button("Agenda", agenda_link)
                            else:
                                st.caption("*(No Link)*")
                            
                            st.divider()
