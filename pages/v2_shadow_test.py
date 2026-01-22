import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v23 Diagnostic", page_icon="🩺", layout="wide")
st.title("🩺 v23: The Developer Diagnostic Tool")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- GLOBAL DEBUG LOG ---
debug_log = []

def log(msg):
    debug_log.append(msg)

# --- 1. THE SCRAPER (Simplified for Debugging) ---
@st.cache_data(ttl=300)
def scrape_public_schedule_debug():
    """
    Scrapes house.vga.virginia.gov and returns the raw lines 
    so we can see why it's missing 'Adjournment' times.
    """
    url = "https://house.vga.virginia.gov/schedule/meetings"
    headers = {'User-Agent': 'Mozilla/5.0'}
    schedule_data = [] # List of {date, raw_text}
    
    try:
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # WE NEED TO SEE THE STRUCTURE
        # Instead of fancy logic, let's just grab the headers and paragraphs
        # to replicate how a human reads it.
        content_blocks = soup.find_all(['h4', 'div', 'p', 'span'])
        
        current_date = "Unknown"
        
        for block in content_blocks:
            text = block.get_text(" ", strip=True)
            if not text: continue
            
            # Detect Date
            if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                current_date = text
                continue
                
            # Capture potential meeting lines
            # Filter out navigation/footer noise
            if len(text) > 5 and len(text) < 200:
                schedule_data.append({
                    "date": current_date,
                    "text": text,
                    "tag": block.name
                })
                
    except Exception as e:
        log(f"Scraper Error: {e}")
        
    return schedule_data

# --- 2. THE API FETCH ---
@st.cache_data(ttl=600) 
def get_api_schedule():
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
        
    # Simple Dedupe
    unique_items = []
    seen = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen:
            seen.add(sig)
            unique_items.append(m)
    return unique_items

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        if href: return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def normalize_name(name):
    """Turns 'House General Laws - Professions' into 'generallawsprofessions'"""
    if not name: return ""
    return re.sub(r'[^a-zA-Z]', '', name.lower().replace("house", "").replace("senate", "").replace("committee", "").replace("subcommittee", ""))

# --- MAIN UI ---

# SIDEBAR DEBUGGER
st.sidebar.header("🛠️ Developer Tools")
show_debug = st.sidebar.checkbox("Show Raw Scraper Data", value=True)
target_committee = st.sidebar.text_input("Filter Debug Log (e.g. 'General Laws')", "")

if st.button("🚀 Run Diagnostic"):
    
    # 1. FETCH DATA
    with st.spinner("Fetching API..."):
        api_meetings = get_api_schedule()
        
    with st.spinner("Scraping Website..."):
        scraped_lines = scrape_public_schedule_debug()
        
    # 2. DEBUG VIEW: RAW SCRAPER OUTPUT
    if show_debug:
        st.subheader("🔍 Raw Scraper Output (What the bot sees)")
        st.info("Look closely here. Is '1/2 hour after adjournment' actually appearing next to the committee name?")
        
        debug_df = []
        for line in scraped_lines:
            # Simple highlight filter
            if target_committee and target_committee.lower() not in line['text'].lower():
                continue
            debug_df.append(line)
            
        st.dataframe(debug_df, use_container_width=True, height=400)

    # 3. BUILD THE MATCHING LOGIC (With Visual Feedback)
    st.subheader("🧩 Match Analysis")
    
    today = datetime.now().date()
    # Filter for next 7 days
    upcoming_api = []
    for m in api_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        if today <= m_date <= today + timedelta(days=7):
            m['CleanDate'] = m_date
            upcoming_api.append(m)
            
    # Display Cards with Match Info
    cols = st.columns(3)
    
    for i, m in enumerate(upcoming_api):
        if i > 20 and not target_committee: break # Limit output unless filtering
        if target_committee and target_committee.lower() not in m['OwnerName'].lower(): continue

        col = cols[i % 3]
        with col:
            with st.container(border=True):
                st.markdown(f"**{m['OwnerName']}**")
                st.caption(f"📅 {m['CleanDate']}")
                
                # THE DEBUG SECTION
                api_time = m.get('ScheduleTime')
                st.text(f"API Time: {api_time}")
                
                # Try to find it in scraped data
                matches = []
                norm_api_name = normalize_name(m['OwnerName'])
                
                for line in scraped_lines:
                    # Check if date matches (rough string match)
                    date_match = m['CleanDate'].strftime("%B %d") in line['date']
                    # Check if name matches
                    name_match = normalize_name(line['text']) in norm_api_name or norm_api_name in normalize_name(line['text'])
                    
                    if date_match and name_match:
                        matches.append(line['text'])
                        
                        # LOOK AROUND NEIGHBORS (The Source of the 7:00 AM Bug?)
                        # We need to find the index of this line to look up/down
                        idx = scraped_lines.index(line)
                        if idx + 1 < len(scraped_lines):
                            matches.append(f"⬇️ NEXT LINE: {scraped_lines[idx+1]['text']}")
                        if idx - 1 >= 0:
                            matches.append(f"⬆️ PREV LINE: {scraped_lines[idx-1]['text']}")

                if matches:
                    st.success("✅ Scraper Matches Found:")
                    for match in matches:
                        st.code(match)
                else:
                    st.error("❌ No Scraper Match Found")
                    st.caption(f"Normalized Name used: {norm_api_name}")
