import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v66 Parent Page Backdoor", page_icon="🚪", layout="wide")
st.title("🚪 v66: The 'Parent Page' Backdoor")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- COMMITTEE MAPPING (The Backdoor Keys) ---
# Maps specific keywords to their House Committee Homepage
COMMITTEE_URLS = {
    "Appropriations": "https://house.vga.virginia.gov/committees/H02",
    "Finance": "https://house.vga.virginia.gov/committees/H09",
    "Courts": "https://house.vga.virginia.gov/committees/H08",
    "Commerce": "https://house.vga.virginia.gov/committees/H11", # Labor & Commerce
    "Education": "https://house.vga.virginia.gov/committees/H07",
    "General": "https://house.vga.virginia.gov/committees/H10", # General Laws
    "Health": "https://house.vga.virginia.gov/committees/H13",
    "Transportation": "https://house.vga.virginia.gov/committees/H22",
    "Safety": "https://house.vga.virginia.gov/committees/H18", # Public Safety
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
    
    keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "conclusion of",
        "commence", "convening", "15 minutes", "30 minutes"
    ]
    
    # 1. Short text check
    if len(clean) < 300 and any(k in lower for k in keywords):
        return clean.strip()

    # 2. Line scan
    for part in re.split(r'[\.\n\r]', clean):
        if any(k in part.lower() for k in keywords):
            return part.strip()

    # 3. Clock Time
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

# --- SOURCE: PARENT PAGE SCRAPER ---
@st.cache_data(ttl=300)
def fetch_committee_page_data(url):
    """
    Scrapes a Committee Homepage (e.g., H02) for meeting times.
    """
    try:
        resp = session.get(url, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # We look for ANY text block that contains a Date and Time
        # This creates a "Bag of Times" for that committee
        page_text = soup.get_text(" ", strip=True)
        
        # Find all date patterns (e.g. "Monday, January 26")
        # And associate the text immediately following it
        schedule_map = {}
        
        # Regex to find dates
        date_matches = list(re.finditer(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', page_text))
        
        for i, match in enumerate(date_matches):
            try:
                date_str = f"{match.group(0)} 2026"
                d_obj = datetime.strptime(date_str, "%A, %B %d %Y").date()
                
                # Get text between this date and the next date
                start = match.end()
                end = date_matches[i+1].start() if i+1 < len(date_matches) else len(page_text)
                block = page_text[start:end]
                
                if d_obj not in schedule_map: schedule_map[d_obj] = []
                schedule_map[d_obj].append(block)
            except: pass
            
        return schedule_map
    except:
        return {}

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

with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# PRE-FETCH PARENT PAGES
# Only fetch pages for committees that actually appear in our list
needed_urls = set()
for m in all_meetings:
    name = m.get("OwnerName", "")
    for key, url in COMMITTEE_URLS.items():
        if key.lower() in name.lower():
            needed_urls.add(url)

parent_page_cache = {}
if needed_urls:
    with st.spinner("Checking Committee Homepages..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(fetch_committee_page_data, url): url for url in needed_urls}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try: parent_page_cache[url] = future.result()
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
    
    final_time = "⚠️ Not Listed on Schedule"
    source_label = "None"
    
    # 1. API COMMENTS
    t = extract_complex_time(api_comments)
    if t:
        final_time = t
        source_label = "Comments"

    # 2. DESCRIPTION MINING
    if "Not Listed" in final_time:
        t = extract_complex_time(description_html)
        if t:
            final_time = t
            source_label = "Description"

    # 3. PARENT PAGE BACKDOOR (The Fix for Appropriations)
    if "Not Listed" in final_time:
        # Find matching URL
        target_url = None
        for key, url in COMMITTEE_URLS.items():
            if key.lower() in name.lower():
                target_url = url
                break
        
        if target_url and target_url in parent_page_cache:
            committee_schedule = parent_page_cache[target_url]
            if m_date in committee_schedule:
                blocks = committee_schedule[m_date]
                # Look for the subcommittee name in the blocks
                # We need a unique identifier from the name (e.g. "Capital Outlay")
                tokens = set(name.replace("-", " ").lower().split())
                tokens.discard("house")
                tokens.discard("committee")
                tokens.discard("subcommittee")
                
                for block in blocks:
                    block_lower = block.lower()
                    # If 2+ keywords match, assume it's the right meeting
                    match_count = sum(1 for token in tokens if token in block_lower)
                    if match_count >= 2:
                        t = extract_complex_time(block)
                        if t:
                            final_time = t
                            source_label = "Parent Page"
                            break

    # 4. API STANDARD
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 
        source_label = "API Standard"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(description_html)
    m['Source'] = source_label
    
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
                
                with st.container(border=True):
                    if "Not Listed" in time_str: st.warning(f"{time_str}")
                    elif "Cancelled" in time_str: st.error(f"{time_str}")
                    else:
                        if len(time_str) > 25: st.markdown(f"**{time_str}**")
                        else: st.markdown(f"### {time_str}")
                    
                    st.markdown(f"**{parent_name}**")
                    if sub_name: st.caption(f"↳ *{sub_name}*")
                            
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
                        
                    if "Not Listed" in time_str:
                        st.caption(f"Src: {m['Source']}")
