import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v99 Fuzzy Linker", page_icon="🔗", layout="wide")
st.title("🔗 v99: The 'Fuzzy Linker' (Token Matching)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

# --- HELPER FUNCTIONS ---
def normalize_name(name):
    if not name: return ""
    # Remove generic words to leave only the unique identifiers
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&", "the", "on"]:
        clean = clean.replace(word, "")
    # Remove extra spaces
    return " ".join(clean.split())

def calculate_similarity(name1, name2):
    """
    Calculates Jaccard Similarity (Token Overlap)
    Returns score between 0.0 and 1.0
    """
    set1 = set(normalize_name(name1).split())
    set2 = set(normalize_name(name2).split())
    
    if not set1 or not set2: return 0.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union

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

# --- 1. COMMITTEE DB FETCH (The Source of Truth for Links) ---
@st.cache_data(ttl=600)
def fetch_committee_database():
    """
    Hits the 'getcommitteelist' endpoint.
    """
    url = "https://lis.virginia.gov/Committee/api/getcommitteelist"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    committee_list = []
    
    try:
        for chamber in ["H", "S"]:
            resp = session.get(url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": chamber}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("Committees", [])
                committee_list.extend(items)
    except Exception as e:
        st.error(f"Committee API Error: {e}")
        
    return committee_list

# --- 2. SCHEDULE FETCH ---
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

with st.spinner("Syncing LIS Databases..."):
    all_raw_items = get_full_schedule()
    committee_db = fetch_committee_database()

today = datetime.now().date()
display_map = {}
seen_sigs = set()

# Debug Info
st.sidebar.info(f"Loaded {len(committee_db)} Committees from DB")

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    # --- FUZZY LINK MATCHING ---
    owner_name = m.get("OwnerName", "Unknown")
    
    best_match = None
    best_score = 0.0
    match_type = "None"
    
    # 1. Try Direct Fuzzy Match
    for db_item in committee_db:
        db_name = db_item.get("CommitteeName", "")
        score = calculate_similarity(owner_name, db_name)
        
        if score > best_score:
            best_score = score
            best_match = db_item
            match_type = "Direct Fuzzy"

    # 2. Parent Fallback (if score is low)
    if best_score < 0.6 and "Subcommittee" in owner_name:
        # Strip "Subcommittee" and try again
        parent_name_guess = owner_name.split("-")[0].strip() # "Senate Finance - Resources" -> "Senate Finance"
        if "Subcommittee" in parent_name_guess: 
             parent_name_guess = parent_name_guess.replace("Subcommittee", "")
        
        for db_item in committee_db:
            db_name = db_item.get("CommitteeName", "")
            # Boost score for parent match
            score = calculate_similarity(parent_name_guess, db_name)
            
            if score > best_score:
                best_score = score
                best_match = db_item
                match_type = "Parent Fallback"

    # 3. EXTRACT LINK
    final_link = None
    if best_score > 0.5: # Acceptance Threshold
        # Prefer LinkUrl (Docket) -> CommitteeUrl (Home)
        raw_link = best_match.get("LinkUrl") or best_match.get("CommitteeUrl")
        if raw_link:
            if raw_link.startswith("/"): raw_link = f"https://lis.virginia.gov{raw_link}"
            final_link = raw_link
            
    # Fallback to Description Link if Probe failed
    if not final_link and m.get("Description"):
        soup_desc = re.search(r'href=[\'"]?([^\'" >]+)', m["Description"])
        if soup_desc: 
            final_link = soup_desc.group(1)
            match_type = "Description Link"

    m["FinalLink"] = final_link
    m["DebugMatch"] = {
        "score": best_score, 
        "matched_name": best_match.get("CommitteeName") if best_match else "None",
        "type": match_type
    }
    
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
                debug = event.get("DebugMatch")
                
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
                    
                    # DEBUG EXPANDER
                    with st.expander("🕵️ Probe Data"):
                        st.write(f"**Method:** {debug['type']}")
                        st.write(f"**Match:** `{debug['matched_name']}`")
                        st.write(f"**Score:** `{debug['score']:.2f}`")
                        if link: st.caption(f"🔗 {link}")
