import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v69 Session Fix", page_icon="🏛️", layout="wide")
st.title("🏛️ v69: Session Defaults & Cancellation Verification")

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

# --- SOURCE: PARENT PAGE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_committee_page_raw(url):
    try:
        resp = session.get(url, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return soup.get_text(" ", strip=True)
    except:
        return ""

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
    if "Cancelled" in time_str: return 9998
    if "Inactive" in time_str or "TBD" in time_str: return 9999
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
        if key.lower() in name.lower():
            needed_urls.add(url)

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
    
    # 1. FLOOR SESSION DEFAULT (Fix for "Inactive" issue)
    if "Convene" in name or "Session" in name:
        if "12:00" not in str(api_time):
             final_time = "12:00 PM (Est.)"
             status_label = "Active" # Force Active

    # 2. API COMMENTS
    if final_time == "TBD":
        t = extract_complex_time(api_comments)
        if t: final_time = t

    # 3. DESCRIPTION MINING
    if final_time == "TBD":
        t = extract_complex_time(description_html)
        if t: final_time = t

    # 4. PARENT PAGE CHECK (Looking for Cancellation)
    if final_time == "TBD" or "Cancel" in final_time:
        target_url = None
        for key, url in COMMITTEE_URLS.items():
            if key.lower() in name.lower():
                target_url = url
                break
        
        if target_url and target_url in parent_cache:
            page_text = parent_cache[target_url]
            # Simple heuristic: If "Cancelled" appears near the date/subcommittee name
            # This is broad but safer than "Inactive"
            if "cancel" in page_text.lower():
                final_time = "❌ Likely Cancelled"
                status_label = "Cancelled"

    # 5. API STANDARD
    if final_time == "TBD" and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    # 6. FINAL STATUS LOGIC
    agenda_link = extract_agenda_link(description_html)
    
    if "Cancel" in final_time or "Cancel" in api_comments:
        final_time = "❌ Cancelled"
        status_label = "Cancelled"
    
    elif final_time == "TBD":
        # If it's a Floor Session, we already set it to Active + 12:00 PM above.
        # If it's a Committee with NO time and NO link, it's likely dead.
        if not agenda_link and "Convene" not in name:
            final_time = "Start Time TBD / Inactive"
            status_label = "Inactive"
        elif not agenda_link:
             # It's a convened session with no link (normal)
             pass 
        else:
            final_time = "⚠️ Time Not Listed"
            status_label = "Warning"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = agenda_link
    m['Status'] = status_label
    
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
                    st.error(f"❌ Cancelled: {full_name}")
                elif status == "Inactive":
                    # Gray / Quiet card for ghost meetings
                    with st.container(border=True):
                        st.caption(f"{time_str}")
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                else:
                    # Normal Active Card (Includes Floor Sessions)
                    with st.container(border=True):
                        if status == "Warning": st.warning(time_str)
                        else: 
                            if len(time_str) > 25: st.markdown(f"**{time_str}**")
                            else: st.markdown(f"### {time_str}")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                                
                        if m['AgendaLink']:
                            st.link_button("View Agenda", m['AgendaLink'])
                        else:
                            # Hide "No Link" text for Floor Sessions to look cleaner
                            if "Convene" not in full_name:
                                st.caption("*(No Link)*")
