import streamlit as st
import requests
import concurrent.futures
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="VA Bill Tracker v206", page_icon="🏛️", layout="wide")
st.title("🏛️ Virginia General Assembly Bill Tracker")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 💎 THE PRIORITY ROUTER ---
# CRITICAL: We check for Specific Subcommittees FIRST.
# If we checked "Appropriations" first, it would steal the link from "Appropriations - Higher Ed".
ROUTER_MAP = [
    # --- HOUSE APPROPRIATIONS SUBS (The most complex ones) ---
    ("Appropriations - Higher Education", "H02006"),
    ("Appropriations - Transportation", "H02007"),
    ("Appropriations - Health", "H02005"),
    ("Appropriations - Commerce", "H02001"),
    ("Appropriations - Compensation", "H02002"),
    ("Appropriations - General", "H02004"),
    ("Appropriations - Elementary", "H02003"),
    
    # --- HOUSE EDUCATION SUBS ---
    ("Education - Higher Education", "H09002"), # Different from Approps Higher Ed!
    ("Education - K-12", "H09001"),
    ("Education - Early Childhood", "H09003"),

    # --- HOUSE P&E SUBS ---
    ("Campaigns and Candidates", "H18003"),
    ("Voting Rights", "H18002"),
    ("Election Administration", "H18001"),
    ("Gubernatorial Appointments", "H18004"),

    # --- HOUSE COURTS SUBS ---
    ("Courts of Justice - Criminal", "H08001"),
    ("Courts of Justice - Civil", "H08002"),
    
    # --- HOUSE GENERAL LAWS SUBS ---
    ("ABC/Gaming", "H11003"),
    ("Housing/Consumer Protection", "H11002"),
    ("Procurement", "H11004"),

    # --- HOUSE TRANSPORTATION SUBS ---
    ("Transportation Infrastructure", "H19002"),
    ("Motor Vehicles", "H19001"),
    ("Highway Safety", "H19004"),
    
    # --- HOUSE HHS SUBS ---
    ("HHS - Health Professions", "H24002"),
    ("HHS - Behavioral Health", "H24003"),
    ("HHS - Social Services", "H24004"),
    ("HHS - Health", "H24001"), # Generic Health sub

    # --- HOUSE PARENTS (Check these LAST) ---
    ("Agriculture", "H01"),
    ("Appropriations", "H02"),
    ("Counties", "H07"),
    ("Courts of Justice", "H08"),
    ("Education", "H09"),
    ("Finance", "H10"),
    ("General Laws", "H11"),
    ("Labor and Commerce", "H14"),
    ("Public Safety", "H15"),
    ("Privileges and Elections", "H18"),
    ("Transportation", "H19"),
    ("Rules", "H20"),
    ("Communications", "H21"),
    ("Health and Human Services", "H24"),

    # --- SENATE (Simple mapping usually works) ---
    ("Senate Agriculture", "S01"),
    ("Senate Commerce", "S02"),
    ("Senate Education", "S04"),
    ("Senate Finance", "S05"),
    ("Senate Courts", "S13"),
    ("Senate General Laws", "S12"),
    ("Senate Local Government", "S07"),
    ("Senate Privileges", "S08"),
    ("Senate Rehabilitation", "S09"),
    ("Senate Transportation", "S11"),
    ("Senate Rules", "S10")
]

def get_smart_link(owner_name):
    """
    Iterates through the Priority Router. 
    Returns the link for the FIRST match found in the Owner Name.
    """
    if not owner_name: return None
    
    # Normalize inputs for comparison
    target = owner_name.replace("House Committee on", "").replace("Committee", "").strip()
    
    for key, code in ROUTER_MAP:
        # Check if our Key (e.g. "Appropriations - Higher Education") is in the Target String
        # We perform a fuzzy check to handle "Subcommittee" suffixes etc.
        
        # 1. Break key into required words (e.g. ["Appropriations", "Higher"])
        required_words = key.split(" - ")
        if len(required_words) == 1:
            required_words = key.split(" ")
            
        # 2. Check if ALL required words are in the target
        if all(word in target for word in required_words):
            return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{code}/committee-details"
            
    return None

# --- API FETCH ---
@st.cache_data(ttl=300)
def fetch_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    events = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            for f in [h, s]:
                if f.result().status_code == 200:
                    events.extend(f.result().json().get("Schedules", []))
    except: pass
    return events

# --- MAIN APP ---
st.markdown("### 📅 Legislative Schedule")

with st.spinner("Syncing Schedule..."):
    raw_events = fetch_schedule()

today = datetime.now().date()
display_map = {}

for m in raw_events:
    if not m: continue
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    # LINK GEN
    m['Link'] = get_smart_link(m.get("OwnerName"))
    
    # TIME FORMAT
    t_str = m.get("ScheduleTime")
    if m.get("IsCancelled"): 
        m['DisplayTime'] = "CANCELLED"
    elif t_str:
        m['DisplayTime'] = t_str
    else:
        m['DisplayTime'] = "Time TBA"
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# DISPLAY
if not display_map:
    st.info("No upcoming meetings found.")
else:
    dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(dates))
    
    for i, dv in enumerate(dates):
        with cols[i]:
            st.markdown(f"### {dv.strftime('%a')}")
            st.caption(dv.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[dv]
            day_events.sort(key=lambda x: x['DisplayTime'])
            
            for e in day_events:
                name = e.get("OwnerName", "Unknown").replace("Committee", "").strip()
                time_s = e['DisplayTime']
                link = e['Link']
                
                if "CANCEL" in str(time_s).upper():
                    st.error(f"❌ **{name}**")
                else:
                    with st.container(border=True):
                        st.markdown(f"**⏰ {time_s}**")
                        # Clean up name for display
                        display_name = name.replace("House ", "").replace("Senate ", "")
                        st.markdown(f"**{display_name}**")
                        
                        if link:
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
