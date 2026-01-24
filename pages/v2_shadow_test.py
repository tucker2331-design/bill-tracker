import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v64 Description Miner", page_icon="⛏️", layout="wide")
st.title("⛏️ v64: The 'Description Miner' & Legacy Override")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    return re.sub('<[^<]+?>', ' ', text).strip() # Strip HTML tags

def extract_time_from_text(text):
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    
    # 1. PRIORITY: Relative Phrases
    # We look for these SPECIFICALLY because these are the ones missing from the API Time field
    relative_keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "15 minutes after"
    ]
    
    # Scan the text for these phrases
    for phrase in relative_keywords:
        if phrase in lower:
            # Return the sentence containing the phrase
            # We split by '.' to get the sentence, or just return the snippet
            idx = lower.find(phrase)
            start = max(0, idx - 10)
            end = min(len(clean), idx + 60)
            return clean[start:end].strip() + "..."

    # 2. FALLBACK: Clock Times
    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

# --- SOURCE: LEGACY LIS "DCO" (Daily Committee Operations) ---
@st.cache_data(ttl=300)
def fetch_legacy_dco(date_obj):
    """
    Fetches the specific LIS daily schedule page (text-only).
    Format: http://lis.virginia.gov/cgi-bin/legp604.exe?261+dco+20260126
    """
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dco+{date_str}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://lis.virginia.gov/'
    }
    
    schedule_map = []
    
    try:
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # This page is usually a simple list or table
        # We grab all text lines to scan them
        text_lines = [line.strip() for line in soup.get_text().splitlines() if line.strip()]
        
        return text_lines # Return raw lines to be searched
    except:
        return []

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

with st.spinner("Fetching Schedule..."):
    all_meetings = get_full_schedule()

today = datetime.now().date()
week_map = {}
for i in range(8): week_map[today + timedelta(days=i)] = []

all_meetings.sort(key=lambda x: len(x.get("OwnerName", "")), reverse=True)

# 1. PRE-FETCH LEGACY DATA (Only for needed days)
# We identify which days have meetings and fetch the DCO page for those days
needed_days = set()
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if raw: needed_days.add(datetime.strptime(raw, "%Y-%m-%d").date())

legacy_data_cache = {}
with st.spinner("Mining Legacy LIS Data..."):
    for day in needed_days:
        if day in week_map: # Only fetch if it's in our display window
            legacy_data_cache[day] = fetch_legacy_dco(day)


# 2. PROCESS MEETINGS
for m in all_meetings:
    raw = m.get("ScheduleDate", "").split("T")[0]
    if not raw: continue
    m_date = datetime.strptime(raw, "%Y-%m-%d").date()
    
    if m_date not in week_map: continue
    
    name = m.get("OwnerName", "")
    if "Caucus" in name or "Press" in name: continue
    
    api_time = m.get("ScheduleTime")
    api_comments = m.get("Comments") or ""
    description = m.get("Description") or ""
    
    final_time = "⚠️ Not Listed on Schedule"
    source = "None"
    
    # Priority 1: API Comments (Often holds 'Upon Adjournment')
    if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
        final_time = api_comments
        source = "API Comments"

    # Priority 2: Description Mining (NEW)
    # Check if the "Description" field itself contains the time text
    elif "adjourn" in description.lower() or "upon" in description.lower():
        extracted = extract_time_from_text(description)
        if extracted:
            final_time = extracted
            source = "API Description"
            
    # Priority 3: Legacy DCO Scraper (NEW)
    elif m_date in legacy_data_cache:
        dco_lines = legacy_data_cache[m_date]
        # Simple fuzzy search in the raw lines
        # Split Committee name to find a unique keyword (e.g. "Compensation")
        tokens = name.split()
        unique_tokens = [t for t in tokens if len(t) > 4 and t.lower() not in ["house", "senate", "committee", "subcommittee"]]
        
        if unique_tokens:
            target_word = unique_tokens[0] # Try the first unique word
            for line in dco_lines:
                if target_word.lower() in line.lower():
                    # If we found the committee name, scan the line for time
                    t = extract_time_from_text(line)
                    if t:
                        final_time = t
                        source = "Legacy LIS"
                        break
            
    # Priority 4: API Time (Standard)
    if "Not Listed" in final_time and api_time and "12:00" not in str(api_time) and "TBA" not in str(api_time):
        final_time = api_time 
        source = "API Standard"

    m['DisplayTime'] = final_time
    m['AgendaLink'] = extract_agenda_link(m.get("Description"))
    m['Source'] = source
    
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
                        st.caption(f"Src: {m['Source']}")
                        # Last Resort Link
                        dco_url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dco+{day.strftime('%Y%m%d')}"
                        st.markdown(f"[Check Official Schedule]({dco_url})")
