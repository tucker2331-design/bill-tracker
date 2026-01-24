import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v65 Unhidden Reader", page_icon="👁️", layout="wide")
st.title("👁️ v65: The 'Unhidden' Reader")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    # Replace <br> with spaces to prevent merging words
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def extract_complex_time(text):
    """
    Hunts for relative time sentences in unstructured text.
    """
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    
    # EXPANDED KEYWORDS (The Fix)
    keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "conclusion of",
        "commence", "convening", "15 minutes", "30 minutes",
        "1/2 hr", "half hour"
    ]
    
    # 1. Check if the whole text is short and contains a keyword
    if len(clean) < 200 and any(k in lower for k in keywords):
        return clean

    # 2. Scan line by line (for longer descriptions)
    # We split by delimiters that might separate the time from other info
    parts = re.split(r'[\.\n\r]', clean)
    for part in parts:
        part_low = part.lower()
        if any(k in part_low for k in keywords):
            return part.strip()

    # 3. Fallback to standard clock time
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

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
    # Rank "Adjournment" times late in the day (e.g. 4pm equivalent)
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

for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    # DATA EXTRACTION
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    description_html = m.get("Description") or ""
    
    final_time = "⚠️ Not Listed on Schedule"
    source_label = "None"
    
    # 1. API COMMENTS (Highest Priority for Relative Times)
    t = extract_complex_time(api_comments)
    if t:
        final_time = t
        source_label = "Comments"

    # 2. DESCRIPTION MINING (If comments failed)
    if "Not Listed" in final_time:
        t = extract_complex_time(description_html)
        if t:
            final_time = t
            source_label = "Description"

    # 3. STANDARD API TIME (If explicit time exists)
    # We prefer the specific "Relative" time over a generic "TBA" if both exist
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
                
                # UNHIDDEN: Show the full text even if it's long
                
                with st.container(border=True):
                    # Time Display Logic
                    if "Not Listed" in time_str: 
                        st.warning(f"{time_str}")
                    elif "Cancelled" in time_str: 
                        st.error(f"{time_str}")
                    else:
                        # If it's a long relative string, just print it bold
                        if len(time_str) > 20:
                             st.markdown(f"**{time_str}**")
                        else:
                             st.markdown(f"### {time_str}")
                    
                    st.markdown(f"**{parent_name}**")
                    if sub_name: st.caption(f"↳ *{sub_name}*")
                            
                    if m['AgendaLink']:
                        st.link_button("View Agenda", m['AgendaLink'])
                    else:
                        st.caption("*(No Link)*")
                        
                    # THE RAW DATA INSPECTOR (For Yellow Cards)
                    if "Not Listed" in time_str:
                        with st.expander("🔍 Show Raw API Data"):
                            st.write("**API Time:**", m.get("ScheduleTime"))
                            st.write("**Comments:**", m.get("Comments"))
                            st.write("**Description HTML:**")
                            st.code(m.get("Description"))
