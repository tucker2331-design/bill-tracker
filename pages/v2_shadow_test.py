import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v62 Agenda Inspector", page_icon="🕵️", layout="wide")
st.title("🕵️ v62: The 'Agenda Inspector'")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=50, pool_maxsize=50)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def extract_time_from_text(text):
    if not text: return None
    clean = text.strip()
    lower = clean.lower()
    
    # 1. PRIORITY: Relative Phrases
    relative_keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of"
    ]
    
    # Check Header area
    if len(clean) < 500:
        if any(k in lower for k in relative_keywords):
            return clean.strip()
            
    # Scan lines
    for line in clean.splitlines():
        l_low = line.lower()
        if any(k in l_low for k in relative_keywords):
            return line.strip()

    # 2. FALLBACK: Clock Times
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

# --- SOURCE 1: AGENDA SCRAPER (With Debug Output) ---
def scrape_agenda_debug(url):
    """
    Returns a dict with debug info + the result
    """
    debug_info = {
        "url": url,
        "status": "Not Run",
        "content_type": "Unknown",
        "snippet": "",
        "found_time": None,
        "error": None
    }
    
    if not url: 
        debug_info["error"] = "No URL provided"
        return debug_info
        
    try:
        resp = session.get(url, timeout=4)
        debug_info["status"] = resp.status_code
        debug_info["content_type"] = resp.headers.get('Content-Type', 'Unknown')
        
        if resp.status_code != 200:
            debug_info["error"] = f"Bad Status: {resp.status_code}"
            return debug_info

        # PDF CHECK
        if 'pdf' in debug_info["content_type"].lower():
             debug_info["error"] = "⚠️ URL is a PDF file (Cannot read text yet)"
             return debug_info
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        full_text = soup.get_text(" ", strip=True)
        debug_info["snippet"] = full_text[:500] # Show first 500 chars
        
        # SEARCH
        header_text = full_text[:1000]
        
        # Explicit Label Search
        match = re.search(r'(?:Time|Start|Convening):\s*(.*?)(?:Place|Location|$)', header_text, re.IGNORECASE)
        if match:
            debug_info["found_time"] = extract_time_from_text(match.group(1))
            
        # Fallback Search
        if not debug_info["found_time"]:
            debug_info["found_time"] = extract_time_from_text(header_text)
            
        return debug_info
        
    except Exception as e:
        debug_info["error"] = str(e)
        return debug_info

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

# 1. IDENTIFY TASKS (No Pre-Fetch in this version to allow Debug)
# We will run the fetch ON DEMAND inside the card if needed, 
# OR we can run it here. For the "Inspector" to work best, let's run it here 
# but save the FULL result object.

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

agenda_debug_results = {}
if tasks:
    st.toast(f"Scanning {len(tasks)} Agendas...", icon="🕵️")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(scrape_agenda_debug, url): mid for mid, url in tasks}
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try: agenda_debug_results[mid] = future.result()
            except: agenda_debug_results[mid] = {"error": "Crash"}

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
    
    debug_data = None
    
    # Priority 1: API Comments
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
    
    # Priority 2: Agenda Reader
    elif m['ScheduleID'] in agenda_debug_results:
        debug_data = agenda_debug_results[m['ScheduleID']]
        if debug_data.get("found_time"):
            final_time = debug_data["found_time"]
            
    # Priority 3: API Time
    elif api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    m['DebugData'] = debug_data
    
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
                    
                    # THE DEBUGGER
                    if "Not Listed" in time_str and m.get('DebugData'):
                        data = m['DebugData']
                        with st.expander("🕵️ Inspect Scraper"):
                            st.caption(f"URL: {data.get('url')}")
                            st.caption(f"Status: {data.get('status')}")
                            st.caption(f"Type: {data.get('content_type')}")
                            
                            if data.get("error"):
                                st.error(data.get("error"))
                            
                            st.markdown("**Raw Text Seen:**")
                            st.code(data.get("snippet", "No text found"))
