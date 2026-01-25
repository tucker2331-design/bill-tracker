import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v83 Scraper Repair", page_icon="🔧", layout="wide")
st.title("⚖️ v83: Back to Basics (Scraper Repair)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- COMMITTEE MAPPING ---
COMMITTEE_URLS = {
    "Appropriations": "https://house.vga.virginia.gov/committees/H02",
    "Finance": "https://house.vga.virginia.gov/committees/H09",
    "Courts": "https://house.vga.virginia.gov/committees/H08",
    "Commerce": "https://house.vga.virginia.gov/committees/H11",
    "Education": "https://house.vga.virginia.gov/committees/H07",
    "General": "https://house.vga.virginia.gov/committees/H10",
    "Health": "https://house.vga.virginia.gov/committees/H13",
    "Transportation": "https://house.vga.virginia.gov/committees/H22",
    "Safety": "https://house.vga.virginia.gov/committees/H18",
}

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def extract_complex_time(text):
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    
    if "cancel" in lower or "postpone" in lower: return "❌ Cancelled"

    keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "conclusion of",
        "commence", "convening", "15 minutes", "30 minutes",
        "1/2 hr", "half hour"
    ]
    
    if len(clean) < 300 and any(k in lower for k in keywords):
        return clean.strip()

    for part in re.split(r'[\.\n\r]', clean):
        if any(k in part.lower() for k in keywords):
            return part.strip()

    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

# --- SOURCE: HOUSE SCHEDULE (Original Method) ---
@st.cache_data(ttl=300)
def fetch_house_schedule_text():
    # This URL was in your original code
    url = "https://house.vga.virginia.gov/schedule/meetings"
    try:
        resp = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        # Get all text, preserving structure slightly
        return soup.get_text("\n", strip=True)
    except Exception as e:
        return f"Error: {e}"

# --- SOURCE: SENATE SCHEDULE (Original Method) ---
@st.cache_data(ttl=300)
def fetch_senate_schedule_text():
    # This URL was in your original code
    url = "https://apps.senate.virginia.gov/Senator/ComMeetings.php"
    try:
        resp = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text("\n", strip=True)
    except Exception as e:
        return f"Error: {e}"

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
    if "TBD" in time_str or "TBA" in time_str: return 9999
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

with st.spinner("Fetching API..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# --- PRE-FETCH SCRAPERS ---
house_text_cache = ""
senate_text_cache = ""

# Only fetch if we actually have floor sessions to check
needs_check = any("Convene" in m.get("OwnerName", "") or "Session" in m.get("OwnerName", "") for m in all_meetings)

if needs_check:
    with st.spinner("Scanning Official Websites..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h_fut = executor.submit(fetch_house_schedule_text)
            s_fut = executor.submit(fetch_senate_schedule_text)
            house_text_cache = h_fut.result()
            senate_text_cache = s_fut.result()

# --- DEVELOPER DEBUG SIDEBAR ---
with st.sidebar:
    st.header("🕵️‍♂️ X-Ray Vision")
    
    st.info("Look below. Do you see the time listed in the raw text?")
    
    with st.expander("Raw Text: House Website"):
        # We only show lines containing "Floor" or "Convene" to keep it readable
        lines = [l for l in house_text_cache.split('\n') if any(x in l for x in ["Floor", "Convene", "Session", "PM", "AM"])]
        st.code("\n".join(lines[:20]), language="text")

    with st.expander("Raw Text: Senate Website"):
         lines = [l for l in senate_text_cache.split('\n') if any(x in l for x in ["Floor", "Convene", "Session", "PM", "AM"])]
         st.code("\n".join(lines[:20]), language="text")

# --- PROCESS MEETINGS ---
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    # 0. IDENTIFY FLOOR SESSIONS
    is_floor_session = "Convene" in name or "Session" in name or "House of Delegates" == name or "Senate" == name
    chamber = "House" if "House" in name else "Senate"
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    description_html = m.get("Description") or ""
    
    final_time = "TBD"
    status_label = "Active"
    decision_log = [] 
    
    # 1. API STANDARD CHECK
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time
        decision_log.append("✅ Found in API 'ScheduleTime'")

    # 2. SCRAPER FIX (v83)
    if final_time == "TBD" and is_floor_session:
        # Select the text cache
        raw_text = house_text_cache if chamber == "House" else senate_text_cache
        
        # 1. Try finding "12:00 PM House Convenes" (Official style)
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)\s+(?:House|Senate)?\s*Convenes', raw_text, re.IGNORECASE)
        if match:
            final_time = match.group(1).upper()
            decision_log.append(f"✅ Found in Website Text (Pattern A)")
        
        # 2. Try finding "Floor Session... 12:00 PM"
        if final_time == "TBD":
            # Look for lines that have both "Floor" and a Time
            for line in raw_text.split('\n'):
                if "Floor" in line or "Session" in line or "Convene" in line:
                    t_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', line)
                    if t_match:
                        final_time = t_match.group(1).upper()
                        decision_log.append(f"✅ Found in Website Text (Pattern B)")
                        break

    # 3. API COMMENTS MINING
    if final_time == "TBD":
        t = extract_complex_time(api_comments)
        if t: 
            final_time = t
            decision_log.append("✅ Found in API 'Comments'")

    # 4. DESCRIPTION MINING
    if final_time == "TBD":
        t = extract_complex_time(description_html)
        if t: 
            final_time = t
            decision_log.append("✅ Found in API 'Description'")

    # 5. CROSS-REFERENCE VALIDATOR (Zombie Check)
    # Skipped for floor sessions
    
    # 6. GHOST PROTOCOL
    agenda_link = extract_agenda_link(description_html)
    
    if "Cancel" in str(final_time) or "Not on" in str(final_time):
        status_label = "Cancelled"
    
    elif final_time == "TBD":
        if not agenda_link:
            if is_floor_session:
                final_time = "Time TBA"
                status_label = "Active"
                decision_log.append("🏛️ Floor Session Confirmed (Waiting for Time)")
            else:
                final_time = "❌ Not Meeting"
                status_label = "Cancelled" 
                decision_log.append("👻 Ghost Protocol: No Link + No Time")
        else:
            final_time = "⚠️ Time Not Listed"
            status_label = "Warning"
            decision_log.append("⚠️ Time missing from all sources")

    m['DisplayTime'] = final_time
    m['AgendaLink'] = agenda_link
    m['Status'] = status_label
    m['Log'] = decision_log
    
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
                
                # Visual logic
                if status == "Cancelled":
                    st.error(f"{time_str}: {full_name}")
                elif status == "Inactive":
                    st.caption(f"{full_name} (Inactive)")
                else:
                    with st.container(border=True):
                        if status == "Warning": st.warning(time_str)
                        else: 
                            if len(str(time_str)) > 25: st.markdown(f"**{time_str}**")
                            else: st.markdown(f"### {time_str}")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                                
                        if m['AgendaLink']:
                            st.link_button("View Agenda", m['AgendaLink'])
                        else:
                            if "Convene" not in full_name and "Session" not in full_name:
                                st.caption("*(No Link)*")
                            
                        with st.expander("🔍 Why?"):
                            for log in m['Log']:
                                st.caption(log)
