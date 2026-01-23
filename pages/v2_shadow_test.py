import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v60 Connection Doctor", page_icon="🩺", layout="wide")
st.title("🩺 v60: The 'Connection Doctor' (Anti-Block)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- GLOBAL DEBUG DATA ---
if 'debug_response' not in st.session_state:
    st.session_state.debug_response = {
        "status": "Not Run",
        "title": "N/A",
        "length": 0,
        "content": ""
    }

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    lower = text.lower()
    lower = lower.replace(".ics", "").replace("view agenda", "")
    lower = re.sub(r'[^a-z0-9\s#]', '', lower)
    tokens = set(lower.split())
    # Keep identifiers like "Committee", "House", "Senate"
    generic_noise = {
        "room", "building", "meeting", "the", "of", "and", "a", "an", 
        "agenda", "view", "video", "public", "testimony", "bill", 
        "caucus", "general", "assembly", "commonwealth", "session"
    }
    return tokens - generic_noise

def extract_relative_time(text):
    lower = text.lower()
    keywords = ["adjournment", "adjourn", "upon", "immediate", "rise of", "recess", "after"]
    if any(k in lower for k in keywords):
        return text.strip()
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', text)
    if match: return match.group(1).upper()
    return None

# --- SCRAPER: LIS MASTER FEED (With Anti-Block Headers) ---
@st.cache_data(ttl=300)
def fetch_lis_data():
    schedule_map = {} 
    
    url = "https://lis.virginia.gov/cgi-bin/legp604.exe?261+sbh+ALL"
    
    # 1. BROWSER MIMIC HEADERS
    # Old CGI scripts often check Referer to prevent hotlinking
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Referer': 'https://lis.virginia.gov/cgi-bin/legp604.exe?261+men+BIL' # Pretend we came from the menu
    }
    
    try:
        resp = session.get(url, headers=headers, timeout=10)
        
        # DEBUG: Capture Vitals
        soup = BeautifulSoup(resp.text, 'html.parser')
        page_title = soup.title.string if soup.title else "No Title Found"
        
        st.session_state.debug_response = {
            "status": resp.status_code,
            "title": page_title.strip(),
            "length": len(resp.text),
            "content": resp.text
        }
        
        # PARSING LOGIC
        rows = soup.find_all('tr')
        current_date = None
        
        for row in rows:
            text = row.get_text(" ", strip=True)
            if not text: continue
            
            # Date Header
            if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                if match:
                    try:
                        raw_s = f"{match.group(0)} 2026"
                        current_date = datetime.strptime(raw_s, "%A, %B %d %Y").date()
                    except: pass
                continue
            
            if not current_date: continue
            
            # Meeting Rows
            cells = row.find_all('td')
            if len(cells) >= 2:
                time_col = cells[0].get_text(" ", strip=True)
                name_col = cells[1].get_text(" ", strip=True)
                
                low_time = time_col.lower()
                is_time = any(x in low_time for x in ['am', 'pm', 'noon', 'adj', 'upon', 'after', 'immediate']) or any(c.isdigit() for c in time_col)
                
                if is_time:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append({
                        "raw_time": time_col,
                        "raw_name": name_col
                    })
                    
    except Exception as e:
        st.session_state.debug_response["status"] = f"ERROR: {str(e)}"
            
    return schedule_map

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    raw_items = []
    
    def fetch_chamber(chamber):
        try:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = session.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("Schedules", [])
                for item in data: item['Chamber'] = chamber
                return data
        except: return []
        return []
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(fetch_chamber, ["H", "S"])
        for r in results: raw_items.extend(r)
        
    unique = []
    seen = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen:
            seen.add(sig)
            unique.append(m)
    return unique

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if any(x in link.get_text().lower() for x in ["agenda", "committee info", "docket"]):
            return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def parse_time_rank(time_str):
    if not time_str or "Not Listed" in time_str or "TBA" in time_str: return 9999
    if "Cancelled" in time_str: return 9998
    clean = time_str.lower().replace(".", "").strip()
    if "adjourn" in clean or "recess" in clean or "upon" in clean or "after" in clean: return 960 
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

with st.spinner("Diagnosing Connection..."):
    all_meetings = get_full_schedule()
    lis_data_map = fetch_lis_data()

# --- SIDEBAR: CONNECTION DOCTOR ---
st.sidebar.header("🩺 Connection Doctor")
debug = st.session_state.debug_response

# 1. Connection Vitals
st.sidebar.markdown(f"**Status Code:** `{debug['status']}`")
st.sidebar.markdown(f"**Page Title:** `{debug['title']}`")
st.sidebar.markdown(f"**Data Size:** `{debug['length']} chars`")

if "Timeout" in debug['title'] or "Error" in debug['title']:
    st.sidebar.error("🚨 BLOCKED: The server returned an error page, not the schedule.")
elif debug['length'] < 5000:
    st.sidebar.warning("⚠️ SUSPICIOUS: Page is very small. Likely a generic landing page.")
else:
    st.sidebar.success("✅ LOOKS GOOD: We likely have the full schedule.")

# 2. Probe
st.sidebar.markdown("---")
probe = st.sidebar.text_input("Probe Content (e.g. 'Finance')")
if probe:
    if probe.lower() in debug['content'].lower():
        st.sidebar.success(f"Found '{probe}' in content!")
    else:
        st.sidebar.error(f"'{probe}' NOT found in content.")

# --- CALENDAR LOGIC ---
today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    final_time = "⚠️ Not Listed on Schedule"
    
    # 1. API COMMENTS
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
        
    # 2. LIS MATCH
    elif m_date in lis_data_map:
        lis_rows = lis_data_map[m_date]
        api_tokens = get_clean_tokens(name)
        
        for row in lis_rows:
            row_tokens = get_clean_tokens(row['raw_name'])
            if api_tokens and api_tokens.issubset(row_tokens):
                t = extract_relative_time(row['raw_time'])
                if t: 
                    final_time = t
                    break

    # FALLBACK
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    week_map[m_date].append(m)

# --- RENDER ---
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
                if len(time_str) > 60: time_str = "See Details"
                
                with st.container(border=True):
                    if "Not Listed" in time_str: st.warning(f"{time_str}")
                    elif "Time Not Listed" in time_str: st.info(f"{time_str}")
                    elif "Cancelled" in time_str: st.error(f"{time_str}")
                    elif len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
                    else: st.markdown(f"**{time_str}**")
                    
                    st.markdown(f"**{parent_name}**")
                    if sub_name: st.caption(f"↳ *{sub_name}*")
                            
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
