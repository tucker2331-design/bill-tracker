import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v98 API Explorer", page_icon="🕵️", layout="wide")
st.title("🕵️ v98: API Explorer (Finding the Missing Links)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- HELPER FUNCTIONS ---
def normalize_name(name):
    if not name: return ""
    # Strict normalization to match "Schedule" names to "Committee" names
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&", "the"]:
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

# --- 1. THE NEW PROBE (Committee API) ---
@st.cache_data(ttl=600)
def fetch_committee_metadata():
    """
    Hits the 'Committee' endpoint to find permanent links.
    """
    base_url = "https://lis.virginia.gov/Committee/api/getcommitteelist"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    metadata_map = {}
    
    try:
        # Fetch both chambers
        for chamber in ["H", "S"]:
            resp = session.get(base_url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": chamber}, timeout=5)
            if resp.status_code == 200:
                items = resp.json() if isinstance(resp.json(), list) else resp.json().get("Committees", [])
                
                for item in items:
                    # We store data keyed by a normalized name for easy matching later
                    raw_name = item.get("CommitteeName", "")
                    norm_name = normalize_name(raw_name)
                    metadata_map[norm_name] = item
                    
    except Exception as e:
        st.error(f"Probe Error: {e}")
        
    return metadata_map

# --- 2. EXISTING SCHEDULE API (The Base) ---
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

with st.spinner("Initializing Schedule..."):
    all_raw_items = get_full_schedule()

with st.spinner("Probing Committee Database..."):
    # This is the NEW call
    committee_db = fetch_committee_metadata()

today = datetime.now().date()
display_map = {}
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    # --- THE MATCHMAKER ---
    # Try to find this schedule item in our new Committee Database
    owner = m.get("OwnerName", "")
    norm_owner = normalize_name(owner)
    
    # Fuzzy-ish lookup in the dictionary
    matched_metadata = {}
    
    # 1. Direct Match
    if norm_owner in committee_db:
        matched_metadata = committee_db[norm_owner]
    else:
        # 2. Partial Match (e.g. "Senate Commerce and Labor" vs "Commerce and Labor")
        for db_name, db_data in committee_db.items():
            if db_name in norm_owner or norm_owner in db_name:
                matched_metadata = db_data
                break
    
    # Store the probe results in the event object
    m['ProbeData'] = matched_metadata
    m['DateObj'] = d
    
    # Clean up Time (Base Logic)
    api_time = m.get("ScheduleTime")
    final_time = api_time
    if not final_time:
        if "Convene" in owner: final_time = "TBA"
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
                
                # Check PROBE DATA for links
                probe = event.get('ProbeData', {})
                # Look for ANYTHING that looks like a URL in the probe result
                found_url = probe.get("LinkUrl") or probe.get("CommitteeUrl") or probe.get("DocketUrl")
                
                # Render Card
                with st.container(border=True):
                    # Time
                    if "TBA" in str(time_disp) or "Not Listed" in str(time_disp):
                        st.warning(f"⚠️ {time_disp}")
                    else:
                        st.markdown(f"**⏰ {time_disp}**")
                    
                    st.markdown(f"**{clean_name}**")
                    
                    # Primary Link Button
                    if found_url:
                        st.link_button("View Info (API Found)", found_url)
                    elif event.get("Description") and "href" in event.get("Description"):
                         st.caption("*(Has Desc Link)*")
                    else:
                         st.caption("*(No Link)*")

                    # THE PROBE EXPANDER
                    with st.expander("🕵️ Probe API"):
                        if probe:
                            st.success("Match Found!")
                            st.json(probe) # Show the RAW JSON so we can see the field names
                        else:
                            st.error("No API Match")
                            st.write(f"Searched for: `{normalize_name(name)}`")
