import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures  # <--- FIXED: Added missing import

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v45 Fixed Lean Master", page_icon="🛠️", layout="wide")
st.title("🛠️ v45: The 'Fixed Lean Master'")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- DEBUG TOGGLE ---
show_debug = st.sidebar.checkbox("Show Raw Scraper Table", value=True)
filter_text = st.sidebar.text_input("Filter Raw Table (e.g. 'Jan 26')")

# --- HELPER: TEXT CLEANING ---
def get_clean_tokens(text):
    if not text: return set()
    lower = text.lower()
    clean_text = lower.replace(".ics", "").replace("view agenda", "")
    clean_text = clean_text.replace("-", " ").replace("#", " ")
    clean_text = re.sub(r'[^a-z0-9\s]', '', clean_text)
    noise = {
        "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "&", "agenda", "view", "video", 
        "signup", "speak", "public", "testimony", "bill", "summit", "caucus",
        "general", "assembly", "commonwealth", "meeting"
    }
    return set(clean_text.split()) - noise

# --- COMPONENT 1: THE LIS "ALL" SCRAPER (Source C) ---
@st.cache_data(ttl=300)
def fetch_lis_schedule():
    """
    Fetches the 'ALL' schedule from LIS to capture House, Senate, and Future Dates.
    """
    schedule_map = {} 
    raw_line_data = [] 
    
    # "ALL" parameter forces the full list (House + Senate + Future)
    url = "https://lis.virginia.gov/cgi-bin/legp604.exe?261+sbh+ALL" 
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        raw_line_data.append({"date": "SYSTEM", "text": f"--- FETCHING: {url} ---", "col1": "", "col2": ""})
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        rows = soup.find_all('tr')
        current_date = None
        
        for row in rows:
            text = row.get_text(" ", strip=True)
            if not text: continue
            
            # 1. DATE DETECTION (LIS Format: "Thursday, January 22, 2026")
            if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                if match:
                    raw_str = f"{match.group(0)} 2026"
                    try: 
                        dt = datetime.strptime(raw_str, "%A, %B %d %Y")
                        current_date = dt.date()
                        raw_line_data.append({"date": str(current_date), "text": "DATE HEADER", "col1": "", "col2": ""})
                    except: pass
                continue
            
            # 2. CAPTURE DATA ROWS
            cells = row.find_all('td')
            if len(cells) >= 2:
                time_text = cells[0].get_text(" ", strip=True)
                info_text = cells[1].get_text(" ", strip=True)
                
                if not current_date: continue
                if not info_text: continue
                
                # Check if it looks like a meeting (Time in col 1)
                if any(c.isdigit() for c in time_text) or "adj" in time_text.lower() or "convenes" in info_text.lower():
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    
                    entry = {
                        "time_raw": time_text,
                        "name_raw": info_text,
                        "tokens": get_clean_tokens(info_text)
                    }
                    schedule_map[current_date].append(entry)
                    
                    raw_line_data.append({
                        "date": str(current_date), 
                        "text": "Meeting", 
                        "col1": time_text, 
                        "col2": info_text
                    })
                    
    except Exception as e:
        raw_line_data.append({"date": "ERROR", "text": str(e), "col1": "", "col2": ""})
            
    return schedule_map, raw_line_data

# --- COMPONENT 2: API FETCH ---
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

# 1. FETCH DATA
with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()
    
with st.spinner("Scraping LIS Master List..."):
    daily_lis_map, raw_debug_data = fetch_lis_schedule()

# --- DEV BOX ---
if show_debug:
    st.subheader("🔍 Raw LIS Table Output")
    display_data = raw_debug_data
    if filter_text:
        display_data = [row for row in raw_debug_data if filter_text.lower() in str(row).lower()]
    st.dataframe(display_data, use_container_width=True, height=400)
    st.divider()

# --- FORECAST LOGIC ---
today = datetime.now().date()
week_map = {}
for i in range(14): 
    week_map[today + timedelta(days=i)] = []
    
valid_meetings = []
all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: week_map[m_date] = []
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    final_time = "⚠️ Not Listed on Schedule"
    
    # 1. API Comments
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
        
    # 2. LIS TABLE SEARCH
    elif m_date in daily_lis_map:
        lis_rows = daily_lis_map[m_date]
        api_tokens = get_clean_tokens(name)
        
        best_row = None
        best_score = 0.0
        
        for row in lis_rows:
            lis_tokens = row['tokens']
            intersection = api_tokens.intersection(lis_tokens)
            
            if not intersection: continue
            
            score = len(intersection) / len(api_tokens)
            if intersection.intersection({'1','2','3','4','5','6'}): score += 0.5
            
            # Boost for subcommittee match
            if "subcommittee" in name.lower() and "subcommittee" in row['name_raw'].lower():
                score += 0.2
            
            if score > best_score and score > 0.65:
                best_score = score
                best_row = row
        
        if best_row:
            final_time = best_row['time_raw']
            if not final_time: final_time = "Time Not Listed"
    
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['CleanDate'] = m_date
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    valid_meetings.append(m)
    week_map[m_date].append(m)

# --- DISPLAY ---
cols = st.columns(7)
days = sorted([d for d in week_map.keys() if d <= today + timedelta(days=6)])

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
