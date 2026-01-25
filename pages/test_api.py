import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v87 Master Calendar", page_icon="📆", layout="wide")
st.title("📆 v87: The Master Calendar (API Logic)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER FUNCTIONS ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def extract_agenda_link(description_html):
    if not description_html: return None
    # Simple regex to find the first link in the description
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

def parse_time_rank(time_str):
    # Sorts events: Floor (Priority -1), Morning, Afternoon, Evening, TBA (Last)
    if not time_str or "TBA" in time_str: return 9999
    try:
        # Standardize "10:00 AM" -> datetime object for sorting
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except: return 9999

# --- API FETCH (The v86 Success Logic) ---
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
            
        return raw_items
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

# --- MAIN APP LOGIC ---

with st.spinner("Syncing Official Schedule..."):
    all_raw_items = get_full_schedule()

# 1. SEPARATE & DEDUPLICATE
# We split the data into "Floor Sessions" (Priority) and "Committees" (Standard)
floor_sessions = []
committees = []
seen_sigs = set() # Signature to prevent duplicates (Date + Time + Name)

for m in all_raw_items:
    # Create a unique signature for this event
    sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs:
        continue # Skip duplicate
    seen_sigs.add(sig)

    name = m.get("OwnerName", "")
    
    # Logic: Identify if this is a Floor Session
    is_floor = "Convene" in name or "Session" in name or name in ["House", "Senate"]
    
    # Clean up the Date
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    m['DateObj'] = datetime.strptime(raw_date, "%Y-%m-%d").date()
    
    # Extract Link early
    m['AgendaLink'] = extract_agenda_link(m.get("Description", ""))

    if is_floor:
        floor_sessions.append(m)
    else:
        committees.append(m)

# 2. FILTER: FUTURE ONLY
today = datetime.now().date()
upcoming_floor = [f for f in floor_sessions if f['DateObj'] >= today]
upcoming_comm = [c for c in committees if c['DateObj'] >= today]

# 3. BUILD THE DISPLAY MAP
# Dictionary: Date -> [List of Events]
display_map = {}

# Add Floor Sessions First (Priority)
for f in upcoming_floor:
    d = f['DateObj']
    if d not in display_map: display_map[d] = []
    f['Type'] = 'Floor'
    display_map[d].append(f)

# Add Committees Second
for c in upcoming_comm:
    d = c['DateObj']
    if d not in display_map: display_map[d] = []
    c['Type'] = 'Committee'
    display_map[d].append(c)

# --- DISPLAY UI ---
if not display_map:
    st.info("No upcoming events found in API.")
else:
    # Get next 7 available dates
    sorted_dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            
            # Sort: Floor first, then committees by time
            def sort_key(x):
                # Floor sessions get rank -1 to always float to top
                if x['Type'] == 'Floor': return -1
                return parse_time_rank(x.get("ScheduleTime"))
            
            day_events.sort(key=sort_key)
            
            for event in day_events:
                name = event.get("OwnerName").replace("Virginia ", "").replace(" of Delegates", "")
                time_val = event.get("ScheduleTime")
                agenda_link = event.get("AgendaLink")
                
                # --- RENDER CARD ---
                if event['Type'] == 'Floor':
                    # FLOOR SESSION CARD (Special Styling)
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        
                        if time_val:
                            st.success(f"⏰ {time_val}")
                        else:
                            # THE TBA LOGIC YOU REQUESTED
                            st.warning("Time TBA")
                            st.caption("*Pending Motion to Adjourn*")
                            
                        if agenda_link:
                             st.link_button("View Calendar", agenda_link)
                
                else:
                    # COMMITTEE CARD (Standard Styling)
                    with st.container():
                        # Time Handling
                        if time_val:
                            st.markdown(f"**{time_val}**")
                        else:
                            st.caption("Time TBA")
                            
                        # Name Handling (Clean up "Committee")
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        
                        # Sub-committee Handling
                        if "Subcommittee" in clean_name:
                            st.caption("↳ Subcommittee")

                        if agenda_link:
                            st.link_button("Agenda", agenda_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        st.divider()
