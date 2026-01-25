import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v80 Final Fix", page_icon="⚖️", layout="wide")
st.title("⚖️ v80: The 'No-Lies' Policy (Final Fix)")

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

# --- SOURCE: OFFICIAL SCHEDULE PAGES (The Bulletin Board) ---
@st.cache_data(ttl=300)
def fetch_chamber_homepage_time(chamber):
    """
    Scrapes the SPECIFIC schedule pages where session times are listed.
    """
    if chamber == "House":
        # UPDATED: The House has a dedicated schedule page (The Bulletin Board)
        url = "https://house.vga.virginia.gov/schedule/meetings"
    else:
        # UPDATED: The Senate time is most reliably found on the LIS homepage
        url = "https://lis.virginia.gov/"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Capture raw text for debug
        raw_preview = text[:2000] # Grab a bit more context
        
        # --- REGEX STRATEGY ---
        # We look for "[Time] [Chamber] Convenes" pattern which is common on these specific pages
        
        if chamber == "House":
            # Matches: "12:00 PM House Convenes" or "House Convenes at 12:00 PM"
            match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP][mM])\.?\s+House\s+Convenes', text, re.IGNORECASE)
            if not match:
                match = re.search(r'House\s+Convenes.*(\d{1,2}:\d{2}\s*[aA|pP][mM])', text[:5000], re.IGNORECASE)
        else:
            # Senate (on LIS homepage): "* 12:00 PM Senate Convenes"
            match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP][mM])\.?\s+Senate\s+Convenes', text, re.IGNORECASE)

        if match:
            # Found it!
            return match.group(1).upper(), f"Found on Official Schedule ({url})", raw_preview
            
        return None, f"Checked Schedule Page ({url}) - No time found", raw_preview
        
    except Exception as e:
        return None, f"Scrape Error: {str(e)}", f"Error: {str(e)}"

# --- SOURCE: LIS DAILY SCHEDULE (DCO) ---
@st.cache_data(ttl=300)
def fetch_lis_daily_schedule(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dco+{date_str}"
    try:
        resp = session.get(url, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text(" ", strip=True)
    except: return ""

# --- SOURCE: PARENT PAGE ---
@st.cache_data(ttl=300)
def fetch_committee_page_raw(url):
    try:
        resp = session.get(url, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text(" ", strip=True)
    except: return ""

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

# --- FAST PRE-FETCH ---
needed_days = set()
needed_urls = set()
needed_homepage_checks = set() 

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw: 
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        if m_date in week_map:
            needed_days.add(m_date)
            if "Convene" in m.get("OwnerName", "") or "Session" in m.get("OwnerName", "") or "House" == m.get("OwnerName", "") or "Senate" == m.get("OwnerName", ""):
                chamber = "House" if "House" in m.get("OwnerName", "") else "Senate"
                needed_homepage_checks.add(chamber)

    name = m.get("OwnerName", "")
    for key, url in COMMITTEE_URLS.items():
        if key.lower() in name.lower(): needed_urls.add(url)

lis_daily_cache = {}
parent_cache = {}
homepage_time_cache = {}
# Debug storage
debug_raw_pages = {}

if needed_days or needed_urls:
    with st.spinner("Checking Sources..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            f_day = {executor.submit(fetch_lis_daily_schedule, day): day for day in needed_days}
            f_url = {executor.submit(fetch_committee_page_raw, url): url for url in needed_urls}
            f_home = {executor.submit(fetch_chamber_homepage_time, c): c for c in needed_homepage_checks}
            
            for f in concurrent.futures.as_completed(f_day):
                try: lis_daily_cache[f_day[f]] = f.result()
                except: pass
            for f in concurrent.futures.as_completed(f_url):
                try: parent_cache[f_url[f]] = f.result()
                except: pass
            for f in concurrent.futures.as_completed(f_home):
                try: 
                    # Capture all 3 return values: Time, Log, RawPreview
                    res = f.result()
                    homepage_time_cache[f_home[f]] = (res[0], res[1]) 
                    debug_raw_pages[f_home[f]] = res[2]
                except: pass

# --- DEVELOPER DEBUG SIDEBAR ---
with st.sidebar:
    st.header("🕵️‍♂️ Developer Probe")
    st.success("v80: Loaded Correctly")
    st.info("The Scraper is now looking at the OFFICIAL schedules, not the tourist homepage.")
    
    if debug_raw_pages:
        st.subheader("🌐 Official Scraper Data")
        for chamber, raw_text in debug_raw_pages.items():
            with st.expander(f"Raw Text: {chamber} Schedule"):
                st.caption(f"Status: {homepage_time_cache[chamber][1]}")
                st.code(raw_text, language="text")

    st.divider()
    st.subheader("📡 Raw API Floor Session")
    
    floor_sessions = [m for m in all_meetings if "Convene" in m.get("OwnerName", "") or "Session" in m.get("OwnerName", "")]
    if floor_sessions:
        for s in floor_sessions:
            with st.expander(f"API JSON: {s.get('OwnerName')}"):
                st.json(s)

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

    # 2. FLOOR SESSION FIX (Honest Mode)
    if final_time == "TBD" and is_floor_session:
        chamber = "House" if "House" in name else "Senate"
        if chamber in homepage_time_cache:
            time_found, source_log = homepage_time_cache[chamber]
            if time_found:
                final_time = time_found
                decision_log.append(f"✅ {source_log}")
            else:
                decision_log.append(f"⚠️ {source_log}")

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
    if final_time == "TBD" and not is_floor_session:
        if m_date in lis_daily_cache:
            official_text = lis_daily_cache[m_date]
            tokens = set(name.replace("-", " ").lower().split())
            tokens -= {"house", "senate", "committee", "subcommittee"}
            
            if tokens:
                found_in_official = False
                for t in tokens:
                    if len(t) > 3 and t in official_text.lower():
                        found_in_official = True
                        break
                
                if not found_in_official:
                    final_time = "❌ Not on Daily Schedule"
                    status_label = "Cancelled"
                    decision_log.append(f"🧟 Zombie Detected: Not in LIS DCO")
                else:
                    decision_log.append("ℹ️ Verified in Official Schedule")

    # 6. GHOST PROTOCOL (The Fix)
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
