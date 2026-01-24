import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v83 Visual Schedule Scraper", page_icon="👁️", layout="wide")
st.title("👁️ v83: The 'Visual Schedule' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("&nbsp;", " ").replace("<br>", " ").replace("</br>", " ")
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

# --- SOURCE: VISUAL SCHEDULE SCRAPER (The Fix) ---
@st.cache_data(ttl=300)
def fetch_visual_schedule_debug(date_obj):
    """
    Scrapes the visual Daily Schedule page (dys) seen in the user's screenshot.
    Returns the full text + the URL for debugging.
    """
    date_str = date_obj.strftime("%Y%m%d")
    # This URL corresponds to the visual list at lis.virginia.gov/schedule
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    
    try:
        resp = session.get(url, timeout=4)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        return text, url
    except Exception as e:
        return f"Error: {str(e)}", url

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

visual_cache = {}
if needed_days:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        f_map = {executor.submit(fetch_visual_schedule_debug, d): d for d in needed_days}
        for f in concurrent.futures.as_completed(f_map):
            visual_cache[f_map[f]] = f.result() # Returns (text, url)

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
    debug_info = None
    
    # A. API FIRST
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time
    
    # B. VISUAL MATCH (For Floor Sessions & Missing Times)
    if final_time == "TBD" and m_date in visual_cache:
        page_text, page_url = visual_cache[m_date]
        
        # If it's a Floor Session, look for explicit "House Convenes" pattern
        if "Convene" in name:
            chamber = "House" if "House" in name else "Senate"
            # Regex to find time before "House Convenes"
            # Matches: "12:00 PM House Convenes"
            pattern = re.compile(rf'(\d{{1,2}}:\d{{2}}\s*[AP]M)\s+{chamber}\s+Convenes', re.IGNORECASE)
            match = pattern.search(page_text)
            
            if match:
                final_time = match.group(1).upper()
            
            # Save debug info for the user
            snippet_start = max(0, page_text.find(f"{chamber} Convenes") - 50)
            snippet = page_text[snippet_start : snippet_start + 150]
            debug_info = {
                "url": page_url,
                "found_time": final_time if final_time != "TBD" else "Not Found",
                "snippet": snippet if snippet else "Text pattern not found in page."
            }

    # C. FALLBACKS
    if final_time == "TBD":
        t = extract_complex_time(m.get("Comments"))
        if t: final_time = t
        
    if final_time == "TBD":
        t = extract_complex_time(desc)
        if t: final_time = t

    # D. STATUS LOGIC
    agenda_link = extract_agenda_link(desc)
    
    if "Cancel" in str(final_time):
        status_label = "Cancelled"
    elif final_time == "TBD":
        if not agenda_link and "Convene" not in name:
             final_time = "❌ Not Meeting"
             status_label = "Cancelled"
        else:
             final_time = "⚠️ Time Not Listed"
             status_label = "Warning"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = agenda_link
    m['Status'] = status_label
    m['Debug'] = debug_info
    
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
                            if len(str(time_str)) > 25: st.markdown(f"**{time_str}**")
                            else: st.markdown(f"### {time_str}")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                                
                        if m['AgendaLink']:
                            st.link_button("View Agenda", m['AgendaLink'])
                        else:
                            if "Convene" not in full_name: st.caption("*(No Link)*")
                            
                        # THE DEV TOOL
                        if m.get('Debug'):
                            with st.expander("🔍 Inspect Scraper"):
                                d = m['Debug']
                                st.write(f"**URL:** [Link]({d['url']})")
                                st.write(f"**Found:** {d['found_time']}")
                                st.markdown("**Raw Text Snippet:**")
                                st.code(d['snippet'])
