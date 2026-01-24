import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v75 Glass Box", page_icon="🪟", layout="wide")
st.title("🪟 v75: The 'Glass Box' Dashboard")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HARDCODED DEFAULTS ---
DEFAULT_TIMES = {
    "House Convenes": "12:00 PM (Est.)",
    "Senate Convenes": "12:00 PM (Est.)",
    "House Session": "12:00 PM (Est.)",
    "Senate Session": "12:00 PM (Est.)"
}

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

# --- HELPER FUNCTIONS ---
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

# --- SOURCE 1: LIS DAILY SCHEDULE (DCO) ---
@st.cache_data(ttl=300)
def fetch_lis_dco(date_obj):
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dco+{date_str}"
    try:
        resp = session.get(url, timeout=3)
        return {"status": resp.status_code, "text": resp.text, "url": url}
    except Exception as e:
        return {"status": "Error", "text": str(e), "url": url}

# --- SOURCE 2: LIS FLOOR CALENDAR (CAL) ---
@st.cache_data(ttl=300)
def fetch_lis_calendar(chamber, date_obj):
    # LIS often uses MMDD for calendars
    date_code = date_obj.strftime("%m%d") 
    chamber_code = "H" if chamber == "House" else "S"
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+cal+{chamber_code}{date_code}"
    
    try:
        resp = session.get(url, timeout=3)
        
        # Check if LIS returned an error page
        if "could not be properly interpreted" in resp.text:
            return {"status": 404, "text": "LIS Error: Date not found", "url": url, "time": None}
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Scan for time
        header = text[:500].lower()
        match = re.search(r'(?:meet|conven|session)\s+(?:at|@)\s*(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', header)
        t = match.group(1).upper() if match else None
        
        return {"status": resp.status_code, "text": text[:200], "url": url, "time": t}
    except Exception as e:
        return {"status": "Error", "text": str(e), "url": url, "time": None}

# --- SOURCE 3: PARENT PAGE ---
@st.cache_data(ttl=300)
def fetch_committee_page(url):
    try:
        resp = session.get(url, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return {"status": resp.status_code, "text": soup.get_text(" ", strip=True), "url": url}
    except: return {"status": "Error", "text": "", "url": url}

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            raw = []
            if h.result().status_code == 200: raw.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw.extend(s.result().json().get("Schedules", []))
            
        unique = []
        seen = set()
        for m in raw:
            sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
            if sig not in seen:
                seen.add(sig)
                unique.append(m)
        return unique
    except: return []

# --- MAIN UI ---

with st.spinner("Initializing Data Sources..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. IDENTIFY NEEDED RESOURCES
needed_days = set()
needed_urls = set()
needed_floors = set()

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
        if d in week_map:
            needed_days.add(d)
            if "Convene" in m.get("OwnerName", ""):
                chamber = "House" if "House" in m.get("OwnerName", "") else "Senate"
                needed_floors.add((chamber, d))
                
    name = m.get("OwnerName", "")
    for key, url in COMMITTEE_URLS.items():
        if key.lower() in name.lower(): needed_urls.add(url)

# 2. PARALLEL FETCH
lis_dco_cache = {}
parent_cache = {}
floor_cache = {}

with st.spinner("Syncing with LIS..."):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        f_dco = {executor.submit(fetch_lis_dco, day): day for day in needed_days}
        f_com = {executor.submit(fetch_committee_page, url): url for url in needed_urls}
        f_cal = {executor.submit(fetch_lis_calendar, c, d): (c,d) for c,d in needed_floors}
        
        for f in concurrent.futures.as_completed(f_dco):
            lis_dco_cache[f_dco[f]] = f.result()
        for f in concurrent.futures.as_completed(f_com):
            parent_cache[f_com[f]] = f.result()
        for f in concurrent.futures.as_completed(f_cal):
            floor_cache[f_cal[f]] = f.result()

# --- SIDEBAR: DATA SOURCES DASHBOARD ---
st.sidebar.header("📊 Data Sources Dashboard")
st.sidebar.markdown("Status of LIS connections for this week:")

# Display Floor Calendar Status
for (chamber, day), data in floor_cache.items():
    status_icon = "🟢" if data['status'] == 200 else "🔴"
    with st.sidebar.expander(f"{status_icon} {chamber} Floor ({day.strftime('%a')})"):
        st.caption(f"Status: {data['status']}")
        st.markdown(f"[View Source Page]({data['url']})")
        if data['status'] == 200:
            st.caption(f"Time Found: {data['time']}")
        else:
            st.error("LIS returned error/empty.")

# --- PROCESS & DISPLAY ---
cols = st.columns(len(week_map)) 
days = sorted(week_map.keys())

for i, day in enumerate(days):
    with cols[i]:
        st.markdown(f"### {day.strftime('%a')}")
        st.caption(day.strftime('%b %d'))
        
        # Daily Schedule Source Link
        if day in lis_dco_cache:
            dco_data = lis_dco_cache[day]
            icon = "🟢" if dco_data['status'] == 200 else "🔴"
            st.markdown(f"[{icon} Check Official Schedule]({dco_data['url']})")
        
        st.divider()
        
        daily_meetings = week_map[day]
        if not daily_meetings:
            st.info("No Committees")
        else:
            for m in daily_meetings:
                name = m.get("OwnerName", "")
                full_name = name
                
                api_time = m.get("ScheduleTime")
                api_comments = m.get("Comments") or ""
                desc = m.get("Description") or ""
                
                final_time = "TBD"
                status = "Active"
                log = []
                
                # --- LOGIC ---
                
                # 1. FLOOR SESSIONS
                if "Convene" in name:
                    chamber = "House" if "House" in name else "Senate"
                    key = (chamber, day)
                    if key in floor_cache and floor_cache[key]['time']:
                        final_time = floor_cache[key]['time']
                        log.append("✅ Found in LIS Floor Calendar")
                    else:
                        final_time = "12:00 PM (Est.)"
                        log.append("⚠️ Not in LIS Calendar (Using Default)")
                
                # 2. COMMITTEES
                else:
                    # Check API
                    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
                        final_time = api_time
                        log.append("✅ API ScheduleTime")
                    elif extract_complex_time(api_comments):
                        final_time = extract_complex_time(api_comments)
                        log.append("✅ API Comments")
                    elif extract_complex_time(desc):
                        final_time = extract_complex_time(desc)
                        log.append("✅ API Description")
                    
                    # 3. ZOMBIE CHECK (Official Schedule)
                    if final_time == "TBD" and day in lis_dco_cache:
                        official_text = lis_dco_cache[day]['text'].lower()
                        # Tokenize name
                        tokens = set(name.replace("-", " ").lower().split())
                        tokens -= {"house", "senate", "committee", "subcommittee"}
                        
                        # Verify existence
                        if tokens:
                            is_official = any(t in official_text for t in tokens if len(t)>3)
                            if not is_official:
                                final_time = "❌ Not on Daily Schedule"
                                status = "Cancelled"
                                log.append("🧟 Zombie: Not in Official LIS Schedule")
                            else:
                                log.append("ℹ️ Verified in Official Schedule")
                
                # 4. GHOST PROTOCOL
                link = None
                soup = BeautifulSoup(desc, 'html.parser')
                for a in soup.find_all('a'):
                    if "agenda" in a.get_text().lower(): link = f"https://house.vga.virginia.gov{a['href']}" if a['href'].startswith("/") else a['href']
                
                if final_time == "TBD":
                    if not link and "Convene" not in name:
                        final_time = "❌ Not Meeting"
                        status = "Cancelled"
                    else:
                        final_time = "⚠️ Time Not Listed"
                        status = "Warning"

                # --- RENDER CARD ---
                if status == "Cancelled":
                    st.error(f"{full_name}")
                    st.caption("Cancelled / Not Meeting")
                else:
                    with st.container(border=True):
                        if status == "Warning": st.warning(final_time)
                        else: st.markdown(f"### {final_time}")
                        
                        st.markdown(f"**{name}**")
                        
                        if link: st.link_button("View Agenda", link)
                        
                        # TRANSPARENCY TOOLS
                        with st.expander("🔍 Verify Data"):
                            st.caption(f"Source Logic: {', '.join(log)}")
                            if day in lis_dco_cache:
                                st.markdown(f"[🔗 Verify on LIS Daily Schedule]({lis_dco_cache[day]['url']})")
                            if "Convene" in name:
                                key = ("House" if "House" in name else "Senate", day)
                                if key in floor_cache:
                                    st.markdown(f"[🔗 Verify on LIS Floor Calendar]({floor_cache[key]['url']})")
