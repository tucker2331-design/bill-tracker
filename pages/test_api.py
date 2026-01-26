import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v98 API Explorer", page_icon="🕵️", layout="wide")
st.title("🕵️ v98: API Explorer (The 'Missing Link' Fix)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

# --- HELPER FUNCTIONS ---
def normalize_name(name):
    if not name: return ""
    # Remove generic words to match "Senate Commerce and Labor" with "Senate Committee on Commerce and Labor"
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&", "the", "on"]:
        clean = clean.replace(word, "")
    return " ".join(clean.split())

def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    if "TBA" in t_upper: return 9999
    if "ADJOURN" in t_upper or "UPON" in t_upper: return 2000 
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- 1. NEW: COMMITTEE API FETCH (The Fix) ---
@st.cache_data(ttl=600)
def fetch_committee_database():
    """
    Hits the 'Committee' API endpoint to find permanent links.
    """
    url = "https://lis.virginia.gov/Committee/api/getcommitteelist"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    committee_map = {}
    
    try:
        # Fetch House and Senate Committees
        for chamber in ["H", "S"]:
            resp = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": chamber}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # Handle API weirdness (sometimes returns list, sometimes dict)
                items = data if isinstance(data, list) else data.get("Committees", [])
                
                for item in items:
                    # Key by Normalized Name for fuzzy matching
                    raw_name = item.get("CommitteeName", "")
                    norm_name = normalize_name(raw_name)
                    committee_map[norm_name] = item
                    
    except Exception as e:
        st.error(f"Committee API Error: {e}")
        
    return committee_map

# --- 2. EXISTING: SCHEDULE API FETCH ---
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
    except: return []

# --- MAIN LOGIC ---

with st.spinner("Fetching Schedule & Committee Database..."):
    all_raw_items = get_full_schedule()
    committee_db = fetch_committee_database()

today = datetime.now().date()
display_map = {}
seen_sigs = set()

# Process Events
for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    # Deduplicate
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    # --- THE LINK FIX ---
    # 1. Start with what the Schedule API gave us
    schedule_link = None
    if m.get("Description") and "href" in m.get("Description"):
        # Quick extract if exists
        soup_desc = re.search(r'href=[\'"]?([^\'" >]+)', m["Description"])
        if soup_desc: schedule_link = soup_desc.group(1)
    
    # 2. PROBE: Look up in Committee DB
    owner_name = m.get("OwnerName", "Unknown")
    norm_owner = normalize_name(owner_name)
    
    # Try to find a match in the DB
    probe_match = {}
    found_db_link = None
    
    # A. Exact Match
    if norm_owner in committee_db:
        probe_match = committee_db[norm_owner]
    else:
        # B. Partial Match (e.g. "Commerce Labor" in "Senate Commerce and Labor")
        for db_key, db_val in committee_db.items():
            if norm_owner in db_key or db_key in norm_owner:
                probe_match = db_val
                break
    
    # 3. EXTRACT LINK FROM PROBE
    if probe_match:
        # Prioritize LinkUrl (usually Docket) -> CommitteeUrl (Homepage)
        found_db_link = probe_match.get("LinkUrl")
        if not found_db_link: found_db_link = probe_match.get("CommitteeUrl")
        
        # FIX: Ensure full URL
        if found_db_link and found_db_link.startswith("/"):
            found_db_link = f"https://lis.virginia.gov{found_db_link}"

    # 4. DECISION TIME
    # Use DB link if Schedule link is missing
    final_link = schedule_link if schedule_link else found_db_link
    m["FinalLink"] = final_link
    m["ProbeData"] = probe_match # Save for the X-Ray
    
    # Time Logic
    api_time = m.get("ScheduleTime")
    final_time = api_time
    if not final_time:
        if "Convene" in owner_name: final_time = "TBA"
        else: final_time = "Not Listed"
    m['DisplayTime'] = final_time
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found.")
else:
    sorted_dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            for event in day_events:
                name = event.get("OwnerName", "Unknown")
                clean_name = name.replace("Committee", "").strip()
                time_disp = event.get("DisplayTime")
                link = event.get("FinalLink")
                probe = event.get("ProbeData")
                
                with st.container(border=True):
                    # Time
                    if "TBA" in str(time_disp) or "Not Listed" in str(time_disp):
                        st.warning(f"⚠️ {time_disp}")
                    else:
                        st.markdown(f"**⏰ {time_disp}**")
                    
                    st.markdown(f"**{clean_name}**")
                    
                    # Link Button
                    if link:
                        st.link_button("View Docket/Agenda", link)
                    else:
                        st.caption("*(No Link)*")
                    
                    # THE X-RAY (Verify the API Match)
                    with st.expander("🕵️ Probe"):
                        if probe:
                            st.success(f"Matched: {probe.get('CommitteeName')}")
                            st.caption(f"DB Link: {probe.get('LinkUrl')}")
                        else:
                            st.error("No API Match")
                            st.caption(f"Searched: {normalize_name(name)}")
