import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v82 Stable + Homepage Fix", page_icon="🏛️", layout="wide")
st.title("🏛️ v82: Stable Core + Homepage Fix")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

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

# --- SOURCE: HOMEPAGE FALLBACK (NEW FIX) ---
def fetch_homepage_time(chamber):
    """
    Fallback: Scrapes house.virginia.gov if LIS fails.
    """
    url = "https://house.virginia.gov/" if chamber == "House" else "https://apps.senate.virginia.gov/"
    try:
        resp = session.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)[:2000] # Top of page
        
        # Look for "Convenes at 12:00 PM"
        match = re.search(r'(?:convenes|session)\s*(?:at|@|:)?\s*(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', text, re.IGNORECASE)
        if match: return match.group(1).upper(), f"Found on Homepage ({url})"
        return None, "Not found on homepage"
    except: return None, "Homepage connection failed"

# --- SOURCE: LIS FLOOR CALENDAR ---
@st.cache_data(ttl=300)
def fetch_floor_session_time(chamber, date_obj):
    """
    Primary: LIS Calendar. Secondary: Homepage.
    """
    # 1. Try LIS Calendar URLs first
    date_code = date_obj.strftime("%m%d") 
    chamber_code = "H" if chamber == "House" else "S"
    urls = [
        f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+cal+{chamber_code}{date_code}",
        f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+doc+{chamber_code}{date_code}"
    ]
    
    debug_text = ""
    for url in urls:
        try:
            resp = session.get(url, timeout=3)
            # If LIS errors out (like in your screenshot), skip immediately
            if "could not be properly interpreted" in resp.text:
                debug_text += f"\nLIS Error at {url}"
                continue
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text(" ", strip=True)
            header = text[:300].lower()
            
            match = re.search(r'(?:meet|conven|session)\s+(?:at|@)\s*(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', header)
            if match: return match.group(1).upper(), "Found in LIS Calendar"
        except: pass
        
    # 2. Fallback to Homepage (The Fix)
    debug_text += "\nTrying Homepage Fallback..."
    home_time, home_msg = fetch_homepage_time(chamber)
    if home_time: return home_time, home_msg
    
    return None, debug_text

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
            h_future = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s_future = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h_future.result().status_code == 200: raw_items.extend(h_future.result().json().get("Schedules", []))
            if s_future.result().status_code == 200: raw_items.extend(s_future.result().json().get("Schedules", []))
            
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

with st.spinner("Fetching API..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# --- SIDEBAR X-RAY TOOL ---
st.sidebar.header("🔍 Data X-Ray")
xray_date = st.sidebar.date_input("Check Floor Session For:", today)
xray_chamber = st.sidebar.selectbox("Chamber", ["House", "Senate"])

if st.sidebar.button("Run X-Ray Scan"):
    time_found, debug_log = fetch_floor_session_time(xray_chamber, xray_date)
    st.sidebar.markdown(f"**Result:** `{time_found if time_found else 'Not Found'}`")
    st.sidebar.caption(debug_log)


# --- FAST PRE-FETCH ---
needed_days = set()
needed_urls = set()
needed_floor_checks = set()

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

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw: 
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        if m_date in week_map:
            needed_days.add(m_date)
            # Identify Floor Sessions to fetch
            if "Convene" in m.get("OwnerName", "") or "Session" in m.get("OwnerName", ""):
                chamber = "House" if "House" in m.get("OwnerName", "") else "Senate"
                needed_floor_checks.add((chamber, m_date))
            
    name = m.get("OwnerName", "")
    for key, url in COMMITTEE_URLS.items():
        if key.lower() in name.lower(): needed_urls.add(url)

lis_daily_cache = {}
parent_cache = {}
floor_session_cache = {}

if needed_days or needed_urls:
    with st.spinner("Scraping LIS..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_day = {executor.submit(fetch_lis_daily_schedule, day): day for day in needed_days}
            future_to_url = {executor.submit(fetch_committee_page_raw, url): url for url in needed_urls}
            future_to_floor = {executor.submit(fetch_floor_session_time, c, d): (c,d) for c,d in needed_floor_checks}
            
            for future in concurrent.futures.as_completed(future_to_day):
                day = future_to_day[future]
                try: lis_daily_cache[day] = future.result()
                except: pass
                
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try: parent_cache[url] = future.result()
                except: pass
                
            for future in concurrent.futures.as_completed(future_to_floor):
                key = future_to_floor[future]
                try: floor_session_cache[key] = future.result()[0] # Get time only
                except: pass

# --- PROCESS MEETINGS ---
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
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

    # 2. FLOOR SESSION FIX (Updated with Fallback)
    if final_time == "TBD" and ("Convene" in name or "Session" in name):
        chamber = "House" if "House" in name else "Senate"
        key = (chamber, m_date)
        
        # Check Scraper (Now includes Homepage Fallback)
        if key in floor_session_cache and floor_session_cache[key]:
            final_time = floor_session_cache[key]
            decision_log.append(f"✅ Found in LIS/Homepage ({chamber})")
        else:
            final_time = "TBD"
            decision_log.append("⚠️ Not found in LIS or Homepage")
        
        status_label = "Active" # Always active

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

    # 5. CROSS-REFERENCE VALIDATOR (Relaxed Matching)
    if final_time == "TBD":
        if m_date in lis_daily_cache:
            official_text = lis_daily_cache[m_date]
            
            # Use strict tokens but require fewer matches
            tokens = set(name.replace("-", " ").lower().split())
            tokens -= {"house", "senate", "committee", "subcommittee"}
            
            if tokens:
                found_in_official = False
                # If ANY valid token (length > 4) is found, we assume it's on the schedule
                # This fixes "House Courts of Justice" vs "Courts of Justice-Civil" mismatch
                for t in tokens:
                    if len(t) > 4 and t in official_text.lower():
                        found_in_official = True
                        break
                
                if not found_in_official:
                    final_time = "❌ Not on Daily Schedule"
                    status_label = "Cancelled"
                    decision_log.append(f"🧟 Zombie Detected: Not in LIS DCO")
                else:
                    decision_log.append("ℹ️ Verified in Official Schedule")

    # 6. GHOST PROTOCOL
    agenda_link = extract_agenda_link(description_html)
    
    if "Cancel" in str(final_time) or "Not on" in str(final_time):
        status_label = "Cancelled"
    
    elif final_time == "TBD":
        if not agenda_link:
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
                            if "Convene" not in full_name: st.caption("*(No Link)*")
                            
                        with st.expander("🔍 Why?"):
                            for log in m['Log']:
                                st.caption(log)
