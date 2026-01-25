import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v88 Final Merge", page_icon="📆", layout="wide")
st.title("📆 v88: The Master Calendar (Smart Text + API)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING (Restored from v83) ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

# --- HELPER: COMPLEX TIME EXTRACTOR (Restored from v83) ---
# This fixes the "TBA" issue for committees meeting "Upon Adjournment"
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
    
    # If the text is short and contains a keyword, return the whole text
    if len(clean) < 150 and any(k in lower for k in keywords):
        return clean.strip()

    # Otherwise, look for standard time formats
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

def extract_agenda_link(description_html):
    if not description_html: return None
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

def parse_time_rank(time_str):
    # Sort Logic: 
    # 0 = Floor Session (Top)
    # 1-1440 = Specific Time (Minutes from midnight)
    # 2000 = "Upon Adjournment" (After morning meetings)
    # 9999 = TBA / Unknown
    
    if not time_str: return 9999
    t_lower = time_str.lower()
    
    if "tba" in t_lower: return 9999
    if "adjourn" in t_lower or "upon" in t_lower or "rise" in t_lower: return 2000 
    
    try:
        # Extract just the time part for sorting
        match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP][mM])', time_str)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    
    return 9999

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

floor_sessions = []
committees = []
seen_sigs = set()

for m in all_raw_items:
    # 1. Clean Data
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    # Deduplicate
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = datetime.strptime(raw_date, "%Y-%m-%d").date()
    m['AgendaLink'] = extract_agenda_link(m.get("Description", ""))
    name = m.get("OwnerName", "")
    
    # 2. Determine Time (The Smart Logic)
    api_time = m.get("ScheduleTime")
    
    # Strategy: If API time is empty, look in the description/comments for "Upon Adjournment"
    final_time = api_time
    if not final_time:
        final_time = extract_complex_time(m.get("Comments"))
    if not final_time:
        final_time = extract_complex_time(m.get("Description"))
        
    m['DisplayTime'] = final_time # Store the extracted string (e.g. "Upon Adjournment")

    # 3. Categorize
    is_floor = "Convene" in name or "Session" in name or name in ["House", "Senate"]
    
    if is_floor:
        floor_sessions.append(m)
    else:
        committees.append(m)

# 4. Filter Future
today = datetime.now().date()
upcoming_floor = [f for f in floor_sessions if f['DateObj'] >= today]
upcoming_comm = [c for c in committees if c['DateObj'] >= today]

# 5. Build Display Map
display_map = {}

for f in upcoming_floor:
    d = f['DateObj']
    if d not in display_map: display_map[d] = []
    f['Type'] = 'Floor'
    display_map[d].append(f)

for c in upcoming_comm:
    d = c['DateObj']
    if d not in display_map: display_map[d] = []
    c['Type'] = 'Committee'
    display_map[d].append(c)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found in API.")
else:
    sorted_dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            
            # Sort: Floor -> Time -> TBA
            def sort_key(x):
                if x['Type'] == 'Floor': return -1
                return parse_time_rank(x.get("DisplayTime"))
            
            day_events.sort(key=sort_key)
            
            for event in day_events:
                name = event.get("OwnerName").replace("Virginia ", "").replace(" of Delegates", "")
                time_display = event.get("DisplayTime")
                agenda_link = event.get("AgendaLink")
                
                if event['Type'] == 'Floor':
                    # FLOOR CARD
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        if time_display:
                            st.success(f"⏰ {time_display}")
                        else:
                            st.warning("Time TBA")
                            st.caption("*Pending Motion to Adjourn*")
                        if agenda_link: st.link_button("View Calendar", agenda_link)
                
                else:
                    # COMMITTEE CARD
                    with st.container():
                        # Display the time, even if it's complex text like "Upon Adjournment"
                        if time_display:
                            # If it's a long sentence, print it as text
                            if len(time_display) > 10:
                                st.markdown(f"**{time_display}**")
                            else:
                                st.markdown(f"**⏰ {time_display}**")
                        else:
                            st.caption("Time TBA")
                            
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        if agenda_link:
                            st.link_button("Agenda", agenda_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        st.divider()
