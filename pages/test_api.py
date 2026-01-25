import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v84 Legislative Command Center", page_icon="🏛️", layout="wide")
st.title("🏛️ v84: Legislative Command Center (Schedule + Bills)")

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

# --- SOURCE 1: VISUAL SCHEDULE (Time/Status Truth) ---
@st.cache_data(ttl=300)
def fetch_visual_schedule(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text("\n", strip=True)
        lines = [clean_html(line) for line in text.splitlines() if line.strip()]
        return lines
    except: return []

# --- SOURCE 2: AGENDA BILL SCRAPER (The "Meld") ---
@st.cache_data(ttl=600)
def fetch_bills_from_agenda(url):
    """
    Visits the agenda URL and extracts bill numbers (HB1234, SB50).
    """
    if not url: return []
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for House/Senate Bills/Resolutions
        # Matches: HB 1234, S.B. 50, HJ 100, etc.
        pattern = r'\b([H|S][B|J|R]\s*\.?\s*\d+)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        # Clean up and deduplicate (e.g. "HB 1234" -> "HB1234")
        cleaned_bills = set()
        for m in matches:
            clean = m.upper().replace(" ", "").replace(".", "")
            cleaned_bills.add(clean)
            
        return sorted(list(cleaned_bills))
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
            
        unique = []
        seen = set()
        for m in raw_items:
            sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
            if sig not in seen:
                seen.add(sig)
                unique.append(m)
        return unique
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
    if "Not" in time_str or "Cancelled" in time_str: return 9998
    if "TBD" in time_str: return 9999
    clean = time_str.lower().replace(".", "").strip()
    if any(x in clean for x in ["adjourn", "upon", "after", "conclusion"]): return 960 
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

with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. PARALLEL PROCESSING (Schedule + Bills)
needed_days = set()
tasks_bills = []

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
        if d in week_map: needed_days.add(d)
    
    # Check if we need to scrape bills
    link = extract_agenda_link(m.get("Description"))
    if link:
        tasks_bills.append(link)

schedule_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    # We use a larger pool to handle bill scraping concurrently with schedule syncing
    with st.spinner("Reading Agendas & Visual Schedules..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            # Task A: Fetch Visual Schedules (Time Truth)
            f_sched = {executor.submit(fetch_visual_schedule, d): d for d in needed_days}
            
            # Task B: Fetch Bills from Agendas (Content Truth)
            f_bills = {executor.submit(fetch_bills_from_agenda, url): url for url in tasks_bills}
            
            # Collect Schedule Results
            for f in concurrent.futures.as_completed(f_sched):
                schedule_cache[f_sched[f]] = f.result()
            
            # Collect Bill Results
            for f in concurrent.futures.as_completed(f_bills):
                try: bill_cache[f_bills[f]] = f.result()
                except: pass

# 2. PROCESS MEETINGS
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    api_time = m.get("ScheduleTime")
    desc = m.get("Description") or ""
    
    final_time = "TBD"
    status_label = "Active"
    
    # A. API FIRST
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time
    
    # B. VISUAL SCHEDULE MATCHING (The Fix for Session/Cancelled)
    if final_time == "TBD" and m_date in schedule_cache:
        lines = schedule_cache[m_date]
        my_tokens = set(normalize_name(name).split())
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            line_tokens = set(normalize_name(line).split())
            
            if my_tokens and my_tokens.issubset(line_tokens):
                prev_line = lines[i-1].lower() if i > 0 else ""
                
                # Check Cancellation
                if "cancel" in line_lower or "cancel" in prev_line:
                    final_time = "❌ Cancelled"
                    status_label = "Cancelled"
                    break
                
                # Check Time
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', line)
                if time_match:
                    final_time = time_match.group(1).upper()
                    break
                    
                # Check Relative Time
                if "adjourn" in line_lower or "upon" in line_lower or "adjourn" in prev_line:
                    final_time = "Upon Adjournment"
                    break

    # C. FALLBACK CLEANUP
    agenda_link = extract_agenda_link(desc)
    
    if final_time == "TBD":
        if "cancel" in desc.lower():
            final_time = "❌ Cancelled"
            status_label = "Cancelled"
        elif "adjourn" in desc.lower():
            final_time = "Upon Adjournment"
        else:
            if not agenda_link and "Convene" not in name:
                final_time = "❌ Not Meeting"
                status_label = "Cancelled"
            else:
                final_time = "⚠️ Time Not Listed"
                status_label = "Warning"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = agenda_link
    m['Status'] = status_label
    m['Bills'] = bill_cache.get(agenda_link, [])
    
    week_map[m_date].append(m)

# --- DISPLAY ---
cols = st.columns(len(week_map)) 
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
                full_name = m.get("OwnerName", "")
                parent_name, sub_name = parse_committee_name(full_name)
                time_str = m['DisplayTime']
                status = m['Status']
                bills = m['Bills']
                
                if status == "Cancelled":
                    st.error(f"{time_str}: {full_name}")
                else:
                    with st.container(border=True):
                        if status == "Warning": st.warning(time_str)
                        else: 
                            if len(str(time_str)) > 25: st.markdown(f"**{time_str}**")
                            else: st.markdown(f"### {time_str}")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        # BILL LISTING LOGIC
                        if bills:
                            with st.expander(f"📜 View {len(bills)} Bills"):
                                st.write(", ".join(bills))
                                if m['AgendaLink']:
                                    st.link_button("Full Agenda", m['AgendaLink'])
                        elif m['AgendaLink']:
                            st.link_button("View Agenda", m['AgendaLink'])
                        else:
                            if "Convene" not in full_name: st.caption("*(No Link)*")
