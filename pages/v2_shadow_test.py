import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v80 Visual Match", page_icon="👁️", layout="wide")
st.title("👁️ v80: The 'Visual Match' Engine")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("&nbsp;", " ").replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def extract_time_from_line(line):
    """
    Extracts time (12:00 PM) or phrases (Upon Adjournment) from a text line.
    """
    clean = clean_html(line).strip()
    lower = clean.lower()
    
    if "cancel" in lower: return "❌ Cancelled"
    
    # 1. Look for explicit times (e.g. 12:00 PM) at the START of the line
    # The Visual Schedule usually puts time first: "12:00 PM House Convenes"
    match = re.match(r'^(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    # 2. Look for keywords anywhere
    keywords = [
        "immediately upon", "upon adjournment", "1/2 hour after", 
        "15 minutes after", "after adjournment", "rise of the"
    ]
    for k in keywords:
        if k in lower:
            # Return a readable snippet
            return "Upon Adjournment/Recess" # Simplify for card title, details in expander
            
    return None

# --- SOURCE: VISUAL SCHEDULE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_visual_schedule(date_obj):
    """
    Fetches the 'dys' (Daily Schedule) page which matches the user's visual screenshot.
    """
    date_str = date_obj.strftime("%Y%m%d")
    # This URL is the text-list version of the visual schedule
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # The page is usually a list of lines. We grab them all.
        # We store them as a list of cleaned strings.
        lines = [clean_html(line) for line in soup.get_text().splitlines() if line.strip()]
        return lines
    except:
        return []

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

with st.spinner("Syncing Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. PRE-FETCH VISUAL SCHEDULES
needed_days = set()
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
        if d in week_map: needed_days.add(d)

visual_schedule_cache = {}
if needed_days:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        f_map = {executor.submit(fetch_visual_schedule, d): d for d in needed_days}
        for f in concurrent.futures.as_completed(f_map):
            visual_schedule_cache[f_map[f]] = f.result()

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
    source_log = []
    
    # A. API FIRST (The Easy Ones)
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time
        source_log.append("✅ Found in API")
    
    # B. VISUAL MATCH (The "Missing Link" Fix)
    if final_time == "TBD" or "Convene" in name:
        if m_date in visual_schedule_cache:
            schedule_lines = visual_schedule_cache[m_date]
            
            # Create tokens for the meeting name (e.g. "House Finance" -> {House, Finance})
            # Remove generic words to avoid false matches
            name_tokens = set(name.replace("-", " ").lower().split())
            name_tokens -= {"house", "senate", "committee", "subcommittee", "room", "building"}
            
            best_match_line = None
            
            # Scan lines in the daily schedule
            for line in schedule_lines:
                line_lower = line.lower()
                # Check if ALL unique tokens are in the line (Strict but Fuzzy)
                # e.g. "Finance" matches "House Finance - Subcommittee #1"
                if name_tokens and name_tokens.issubset(set(line_lower.split())):
                    
                    # Special check for "Cancelled" lines
                    if "cancel" in line_lower:
                        final_time = "❌ Cancelled"
                        status_label = "Cancelled"
                        source_log.append(f"✅ Matched 'Cancelled' in Schedule: '{line[:30]}...'")
                        break
                    
                    # Extract time from this line
                    extracted = extract_time_from_line(line)
                    if extracted:
                        final_time = extracted
                        source_log.append(f"✅ Matched Visual Schedule: '{line[:30]}...'")
                        break
    
    # C. GHOST PROTOCOL (Cleanup)
    if final_time == "TBD":
        # Check description for hidden gems
        if "cancel" in desc.lower():
            final_time = "❌ Cancelled"
            status_label = "Cancelled"
        elif "adjourn" in desc.lower():
            final_time = "Upon Adjournment"
        else:
            # If still TBD:
            agenda_link = extract_agenda_link(desc)
            if not agenda_link and "Convene" not in name:
                final_time = "❌ Not Meeting"
                status_label = "Cancelled"
            else:
                final_time = "⚠️ Time Not Listed"
                status_label = "Warning"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(desc)
    m['Status'] = status_label
    m['Log'] = source_log
    
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
                
                if status == "Cancelled":
                    st.error(f"{time_str}: {full_name}")
                else:
                    with st.container(border=True):
                        if status == "Warning": st.warning(time_str)
                        else: 
                            # Handle long relative times
                            if len(str(time_str)) > 25: st.markdown(f"**{time_str}**")
                            else: st.markdown(f"### {time_str}")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                                
                        if m['AgendaLink']:
                            st.link_button("View Agenda", m['AgendaLink'])
                        else:
                            if "Convene" not in full_name: st.caption("*(No Link)*")
                            
                        # Debug info for transparency
                        if status == "Warning" or "Convene" in full_name:
                             with st.expander("Src"):
                                 for l in m['Log']: st.caption(l)
