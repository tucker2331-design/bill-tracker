import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v71 Ghost Protocol", page_icon="👻", layout="wide")
st.title("👻 v71: The 'Ghost Protocol' (Empty = Cancelled)")

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

# --- SOURCE: PARENT PAGE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_committee_page_raw(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    try:
        resp = session.get(url, headers=headers, timeout=5)
        if resp.status_code != 200: return f"ERROR: Status {resp.status_code}"
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text(" ", strip=True)
    except Exception as e: return f"ERROR: {str(e)}"

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        h_resp = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
        s_resp = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
        
        raw_items = []
        if h_resp.status_code == 200: raw_items.extend(h_resp.json().get("Schedules", []))
        if s_resp.status_code == 200: raw_items.extend(s_resp.json().get("Schedules", []))
        
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
    if "Not Meeting" in time_str or "Cancelled" in time_str: return 9998
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

with st.spinner("Processing Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# PRE-FETCH PARENT PAGES
needed_urls = set()
for m in all_meetings:
    name = m.get("OwnerName", "")
    for key, url in COMMITTEE_URLS.items():
        if key.lower() in name.lower(): needed_urls.add(url)

parent_cache = {}
if needed_urls:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(fetch_committee_page_raw, url): url for url in needed_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try: parent_cache[url] = future.result()
            except: pass

# PROCESS MEETINGS
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

    # 2. FLOOR SESSION DEFAULTS
    if final_time == "TBD":
        for key, default_time in DEFAULT_TIMES.items():
            if key.lower() in name.lower():
                final_time = default_time
                status_label = "Active"
                decision_log.append(f"✅ Applied Default Time for '{key}'")
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

    # 5. PARENT PAGE CHECK
    if final_time == "TBD" or "Cancel" in final_time:
        target_url = None
        for key, url in COMMITTEE_URLS.items():
            if key.lower() in name.lower():
                target_url = url
                break
        if target_url and target_url in parent_cache and "cancel" in parent_cache[target_url].lower():
            decision_log.append("⚠️ Parent page mentions 'Cancelled'")

    # 6. FINAL STATUS (The Ghost Protocol)
    agenda_link = extract_agenda_link(description_html)
    
    if "Cancel" in str(final_time) or "Cancel" in api_comments:
        final_time = "❌ Cancelled"
        status_label = "Cancelled"
    
    elif final_time == "TBD":
        if not agenda_link:
            # GHOST PROTOCOL: Empty API + No Link = Not Meeting
            final_time = "❌ Not Meeting"
            status_label = "Cancelled" 
            decision_log.append("👻 Ghost Protocol: No Link + No Time = Not Meeting")
        else:
            final_time = "⚠️ Time Not Listed"
            status_label = "Warning"
            decision_log.append("⚠️ Link Exists but Time Missing")

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
                    # We shouldn't see this anymore, merged into Cancelled
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
                            st.caption("*(No Link)*")
                            
                        with st.expander("🔍 Why?"):
                            for log in m['Log']:
                                st.caption(log)
