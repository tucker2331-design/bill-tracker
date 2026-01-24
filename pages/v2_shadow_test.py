import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v63 API Hunter", page_icon="🔓", layout="wide")
st.title("🔓 v63: The 'API Hunter' (Backdoor Access)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

# --- HELPER: TIME PARSING ---
def extract_time_from_json(data):
    """
    Scans a JSON object for time-related keys.
    """
    if not data: return None
    
    # Common keys in JSON APIs
    keys_to_check = ['Time', 'DisplayTime', 'MeetingTime', 'Description', 'Comments']
    
    # 1. Check Top Level
    for k in keys_to_check:
        if k in data and data[k]:
            t = str(data[k])
            # Check for relative phrases or clock time
            if any(x in t.lower() for x in ['adj', 'upon', 'immediate']): return t
            if re.search(r'\d{1,2}:\d{2}', t): return t
            
    return None

# --- SOURCE 1: API HUNTER ---
def hunt_agenda_api(agenda_url):
    """
    Extracts the ID from the URL and probes hidden API endpoints.
    """
    debug_log = []
    
    # 1. Extract ID (e.g. 5229 from .../agendas/5229)
    match = re.search(r'/agendas/(\d+)', agenda_url)
    if not match: 
        return {"error": "Could not parse Agenda ID", "log": debug_log}
    
    agenda_id = match.group(1)
    
    # 2. PROBE COMMON PATTERNS
    # Based on standard .NET / Modern Web API structures
    patterns = [
        f"https://house.vga.virginia.gov/api/agendas/{agenda_id}",
        f"https://house.vga.virginia.gov/api/committeeagendas/{agenda_id}",
        f"https://house.vga.virginia.gov/agendas/api/{agenda_id}"
    ]
    
    for api_url in patterns:
        try:
            resp = session.get(api_url, timeout=3)
            debug_log.append(f"Tried {api_url} -> {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    json_data = resp.json()
                    # We found JSON!
                    time_found = extract_time_from_json(json_data)
                    return {
                        "success": True,
                        "found_time": time_found,
                        "json_dump": json_data,
                        "used_url": api_url
                    }
                except:
                    pass # Not JSON
        except: pass
        
    return {"success": False, "log": debug_log}

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

with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. IDENTIFY TASKS (API HUNTER)
tasks = []
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    api_time = m.get("ScheduleTime")
    agenda_link = extract_agenda_link(m.get("Description"))
    
    if (not api_time or "12:00" in str(api_time) or "TBA" in str(api_time)) and agenda_link:
        tasks.append((m['ScheduleID'], agenda_link))

# 2. EXECUTE HUNTER
hunter_results = {}
if tasks:
    st.toast(f"Hunting APIs for {len(tasks)} agendas...", icon="🔓")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(hunt_agenda_api, url): mid for mid, url in tasks}
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try: hunter_results[mid] = future.result()
            except: hunter_results[mid] = None

# 3. RENDER
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
    
    debug_info = None
    
    # Priority 1: API Comments
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
    
    # Priority 2: API Hunter (New Fix)
    elif m['ScheduleID'] in hunter_results:
        res = hunter_results[m['ScheduleID']]
        debug_info = res # Store for inspector
        if res and res.get("success") and res.get("found_time"):
             final_time = res["found_time"]
            
    # Priority 3: API Time
    elif api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    m['DebugInfo'] = debug_info
    
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
                    
                    # INSPECTOR
                    if "Not Listed" in time_str and m.get('DebugInfo'):
                        d = m['DebugInfo']
                        with st.expander("🔓 API Probe"):
                            if d.get("success"):
                                st.success(f"JSON Found! ({d['used_url']})")
                                st.json(d['json_dump'])
                            else:
                                st.error("No JSON Endpoint Found.")
                                for line in d.get("log", []):
                                    st.caption(line)
