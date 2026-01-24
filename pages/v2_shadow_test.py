import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v76 Session Probe", page_icon="🔬", layout="wide")
st.title("🔬 v76: The 'Session Time Probe'")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

# --- PROBE TOOLS ---
def test_lis_url(url_pattern, date_obj, chamber):
    """
    Tests a specific LIS URL pattern to see if it returns valid data.
    """
    # Generate Date Strings
    mmdd = date_obj.strftime("%m%d")
    yyyymmdd = date_obj.strftime("%Y%m%d")
    c_code = "H" if chamber == "House" else "S"
    
    # Replace placeholders
    url = url_pattern.replace("{SESSION}", SESSION_CODE)
    url = url.replace("{CHAMBER}", c_code)
    url = url.replace("{MMDD}", mmdd)
    url = url.replace("{YYYYMMDD}", yyyymmdd)
    
    try:
        resp = session.get(url, timeout=3)
        status = resp.status_code
        
        # Check for LIS specific error text even if status is 200
        if "query could not be properly interpreted" in resp.text:
            return {"status": "Error (LIS Query)", "url": url, "snippet": "LIS Database rejected the query format."}
        if "not available" in resp.text.lower():
            return {"status": "Empty (Not Pub)", "url": url, "snippet": "Page says 'Not Available'."}
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)[:200]
        
        return {"status": status, "url": url, "snippet": text}
    except Exception as e:
        return {"status": "Connection Fail", "url": url, "snippet": str(e)}

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            raw = []
            if h.result().status_code == 200: raw.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw.extend(s.result().json().get("Schedules", []))
            
        unique = []
        seen = set()
        for m in raw:
            sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
            if sig not in seen:
                seen.add(sig)
                unique.append(m)
        return unique
    except: return []

# --- MAIN UI ---

with st.spinner("Loading..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# --- SIDEBAR: SESSION PROBE ---
st.sidebar.header("🔬 Session Time Probe")
st.sidebar.info("Use this to find the correct URL for the Floor Calendar.")

probe_date = st.sidebar.date_input("Target Date", today)
probe_chamber = st.sidebar.selectbox("Chamber", ["House", "Senate"])

# PATTERNS TO TEST
patterns = [
    ("Standard Calendar (MMDD)", "https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION}+cal+{CHAMBER}{MMDD}"),
    ("Full Date Calendar (YYYYMMDD)", "https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION}+cal+{CHAMBER}{YYYYMMDD}"),
    ("Docket (MMDD)", "https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION}+doc+{CHAMBER}{MMDD}"),
    ("Daily Schedule (DCO)", "https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION}+dco+{YYYYMMDD}"),
    ("Chamber Home", "https://house.virginia.gov/" if probe_chamber == "House" else "https://apps.senate.virginia.gov/")
]

if st.sidebar.button("🚀 Launch Probe"):
    st.sidebar.markdown("---")
    for name, pattern in patterns:
        res = test_lis_url(pattern, probe_date, probe_chamber)
        
        if res['status'] == 200 and "Error" not in str(res['status']):
            st.sidebar.success(f"✅ {name}")
        else:
            st.sidebar.error(f"❌ {name}")
            
        with st.sidebar.expander("Details"):
            st.write(f"**URL:** `{res['url']}`")
            st.write(f"**Status:** {res['status']}")
            st.write(f"**Seen:** {res['snippet']}")


# --- MAIN LIST (SAFE MODE) ---
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    if m_date not in week_map: continue
    
    api_time = m.get("ScheduleTime")
    name = m.get("OwnerName", "")
    
    # Default display
    display_time = "TBD"
    status_color = "warning" # Yellow
    
    # 1. API Time
    if api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        display_time = api_time
        status_color = "success"
        
    # 2. Check Description for "Cancelled" (Safe check only)
    desc = m.get("Description") or ""
    if "cancel" in desc.lower():
        display_time = "❌ Cancelled"
        status_color = "error"

    m['DisplayTime'] = display_time
    m['Color'] = status_color
    week_map[m_date].append(m)

# DISPLAY
cols = st.columns(len(week_map)) 
days = sorted(week_map.keys())

for i, day in enumerate(days):
    with cols[i]:
        st.markdown(f"### {day.strftime('%a')}")
        st.caption(day.strftime('%b %d'))
        st.divider()
        
        for m in week_map[day]:
            t = m['DisplayTime']
            c = m['Color']
            
            with st.container(border=True):
                if c == "error": st.error(f"{t}")
                elif c == "warning": st.warning(f"⚠️ {t}")
                else: st.markdown(f"**{t}**")
                
                st.markdown(f"**{m['OwnerName']}**")
                
                # Check link
                soup = BeautifulSoup(m.get("Description") or "", 'html.parser')
                link = None
                for a in soup.find_all('a'):
                    if "agenda" in a.get_text().lower(): link = f"https://house.vga.virginia.gov{a['href']}" if a['href'].startswith("/") else a['href']
                
                if link: st.link_button("View Agenda", link)
                else: st.caption("(No Link)")
