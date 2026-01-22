import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v52 DNA Matcher", page_icon="🧬", layout="wide")
st.title("🧬 v52: The 'DNA' Matcher & Live Inspector")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: DNA EXTRACTION ---
def get_dna_tokens(text):
    """
    Extracts ONLY the high-value, unique keywords.
    Ignores common parliamentary words.
    """
    if not text: return set()
    lower = text.lower()
    
    # 1. Clean
    lower = lower.replace(".ics", "").replace("view agenda", "")
    lower = re.sub(r'[^a-z0-9\s]', '', lower)
    
    # 2. Split
    tokens = set(lower.split())
    
    # 3. DNA FILTER (Ignore these common words)
    # We want to match on 'Compensation', 'Retirement', 'Innovation', etc.
    # We DO NOT want to match on 'House', 'Senate', 'Committee' because everyone has those.
    generic_dna = {
        "house", "senate", "committee", "subcommittee", "room", "building", 
        "meeting", "the", "of", "and", "a", "an", "&", "agenda", "view", 
        "video", "public", "testimony", "bill", "caucus", "general", 
        "assembly", "commonwealth", "session", "convenes", "adjourned"
    }
    
    return tokens - generic_dna

def extract_time_from_block(block_text):
    lower_text = block_text.lower()
    if "cancel" in lower_text: return "❌ Cancelled"
    if "noon" in lower_text: return "12:00 PM"
    
    if "adjourn" in lower_text or "recess" in lower_text:
        for line in block_text.splitlines():
            if "adjourn" in line.lower() or "recess" in line.lower():
                return line.strip()

    time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', block_text)
    if time_match: return time_match.group(1).upper()
    return None

# --- SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_house_blocks():
    schedule_map = {} 
    
    today = datetime.now().date()
    days_ahead = 0 - today.weekday() if today.weekday() > 0 else 0 
    if days_ahead <= 0: days_ahead += 7
    next_monday = today + timedelta(days=days_ahead)
    
    # Try multiple formats to force the server to respond
    urls = [
        ("Current", "https://house.vga.virginia.gov/schedule/meetings"),
        ("Next (US)", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%m/%d/%Y')}"),
        ("Next (ISO)", f"https://house.vga.virginia.gov/schedule/meetings?date={next_monday.strftime('%Y-%m-%d')}")
    ]
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for label, url in urls:
        try:
            resp = session.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            all_tags = soup.find_all(['div', 'span', 'p', 'h4', 'h5', 'a', 'li'])
            
            current_date = None
            current_block_lines = []
            
            for tag in all_tags:
                text = tag.get_text(" ", strip=True)
                if not text: continue
                
                # DATE DETECTION
                if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                    match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday),\s+([A-Za-z]+)\s+(\d{1,2})', text)
                    if match:
                        if current_date and current_block_lines:
                            if current_date not in schedule_map: schedule_map[current_date] = []
                            schedule_map[current_date].append("\n".join(current_block_lines))
                            current_block_lines = []
                        
                        raw_str = f"{match.group(0)} 2026"
                        try: dt = datetime.strptime(raw_str, "%A, %B %d %Y")
                        except: 
                            try: dt = datetime.strptime(raw_str, "%A, %b %d %Y")
                            except: continue
                        current_date = dt.date()
                        continue

                if not current_date: continue
                
                # BLOCK LOGIC
                low_text = text.lower()
                is_start = "convenes" in low_text or "session" in low_text
                is_end = ".ics" in low_text or "archived" in low_text or "pledge" in low_text
                
                if is_start and current_block_lines:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append("\n".join(current_block_lines))
                    current_block_lines = []

                current_block_lines.append(text)
                
                if is_end:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append("\n".join(current_block_lines))
                    current_block_lines = []
            
            if current_date and current_block_lines:
                if current_date not in schedule_map: schedule_map[current_date] = []
                schedule_map[current_date].append("\n".join(current_block_lines))
                
        except: pass
            
    return schedule_map

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

# 1. FETCH
with st.spinner("Loading Data..."):
    all_meetings = get_full_schedule()
    daily_blocks_map = fetch_house_blocks()

# --- LIVE INSPECTOR (SIDEBAR) ---
st.sidebar.header("🧬 Live DNA Inspector")
st.sidebar.info("Type a word (e.g. 'Compensation') to see if it exists in the raw data.")
debug_query = st.sidebar.text_input("DNA Probe:")
if debug_query:
    st.sidebar.markdown(f"**Probing for: '{debug_query}'**")
    probe_dna = get_dna_tokens(debug_query)
    st.sidebar.write(f"**DNA:** `{probe_dna}`")
    
    hits = 0
    for date, blocks in daily_blocks_map.items():
        for block in blocks:
            block_dna = get_dna_tokens(block)
            if probe_dna.issubset(block_dna):
                hits += 1
                with st.sidebar.expander(f"Hit #{hits} ({date.strftime('%a')})"):
                    st.write(block)
    if hits == 0:
        st.sidebar.error("No DNA matches found!")

# --- CALENDAR LOGIC ---
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
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    final_time = "⚠️ Not Listed on Schedule"
    
    # --- MATCH LOGIC ---
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
    
    elif m_date in daily_blocks_map:
        blocks = daily_blocks_map[m_date]
        api_dna = get_dna_tokens(name) # Extract rare keywords only
        
        # DEBUG DATA
        m['DNA_Tokens'] = api_dna
        
        for block_text in blocks:
            block_dna = get_dna_tokens(block_text)
            
            # THE DNA TEST:
            # Does the block contain ALL the rare keywords from the API?
            # Example: API={compensation, retirement}. Block={compensation, retirement, askew}.
            # {comp, ret} is subset of {comp, ret, askew} -> TRUE.
            if api_dna.issubset(block_dna):
                extracted_time = extract_time_from_block(block_text)
                final_time = extracted_time if extracted_time else "Time Not Listed"
                break
            
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 

    m['DisplayTime'] = final_time
    m['CleanDate'] = m_date
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    
    week_map[m_date].append(m)

# --- RENDER ---
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
                    
                    if "Not Listed" in time_str:
                         with st.expander("🧬 DNA Mismatch"):
                             st.write(f"Required DNA: `{m.get('DNA_Tokens', 'None')}`")
