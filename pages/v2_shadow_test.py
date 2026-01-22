import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v22 Omni-Scraper", page_icon="🧿", layout="wide")
st.title("🧿 v22: The Omni-Directional Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT NORMALIZATION ---
def get_significant_words(text):
    if not text: return set()
    noise = {"house", "senate", "committee", "subcommittee", "room", "building", "meeting", "the", "of", "and", "&", "-", "agenda", "view", "video"}
    words = set(re.sub(r'[^a-zA-Z\s]', '', text.lower()).split())
    return words - noise

# --- COMPONENT 1: THE OMNI-SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_master_times():
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        current_date = None
        # Get text lines preserving layout
        text_blob = soup.get_text("\n")
        lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        # We need to know valid committee names to identify "Anchors"
        # Since we don't have the API list yet, we look for "Committee" or "Subcommittee" keywords
        # or we scan for lines that look like titles.
        
        for i, line in enumerate(lines):
            # 1. Detect Date Header
            if any(day in line for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    # "Wednesday, January 21, 2026"
                    clean_date = line.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                except: pass
            
            if not current_date: continue

            # 2. PATTERN A: SENATE STYLE (Time matches first)
            # "9:00 AM" ... next line "Senate Finance"
            if any(x in line.lower() for x in ["am", "pm", "noon"]) and "time" not in line.lower():
                # Check Next Line for Committee
                if i + 1 < len(lines):
                    potential_comm = lines[i+1]
                    # Validate it looks like a committee
                    if "senate" in potential_comm.lower() or "house" in potential_comm.lower():
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append({
                            "words": get_significant_words(potential_comm),
                            "time": line,
                            "source": "Senate-Style (Time First)"
                        })

            # 3. PATTERN B: HOUSE STYLE (Committee matches first)
            # "House General Laws" ... next line "Room B" ... next line "1/2 hr after adjournment"
            if "house" in line.lower() or "senate" in line.lower():
                # Potential Committee Header found. Look DOWN for time.
                # Scan next 3 lines
                found_time = None
                for offset in range(1, 4):
                    if i + offset >= len(lines): break
                    sub_line = lines[i + offset]
                    sub_lower = sub_line.lower()
                    
                    # Look for Time Keywords
                    if any(k in sub_lower for k in ["adjournment", "recess", "upon", "immediately", "after", "am", "pm"]):
                        found_time = sub_line
                        break
                
                if found_time:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append({
                        "words": get_significant_words(line),
                        "time": found_time,
                        "source": "House-Style (Time Below)"
                    })

    except Exception as e: 
        print(e)
    return schedule_map

# --- COMPONENT 2: API FETCH (Source A) ---
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
        text = link.get_text().lower()
        if any(x in text for x in ["agenda", "committee info", "docket"]):
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        
        def natural_sort_key(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
        return sorted(list(clean_bills), key=natural_sort_key)
    except: return []

def fetch_bills_parallel(meetings_list):
    tasks = []
    for m in meetings_list:
        if m.get('AgendaLink'): tasks.append((m, m['AgendaLink']))
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(scan_agenda_page, url): m['ScheduleID'] for m, url in tasks}
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try: results[mid] = future.result()
            except: results[mid] = []
    return results

def parse_time_rank(time_str):
    if not time_str: return 9999
    clean = time_str.lower().replace(".", "").strip()
    # Adjournment meetings go LATE (4:00 PM = 960 mins)
    if "adjourn" in clean or "recess" in clean or "upon" in clean or "after" in clean: return 960 
    if "tba" in clean: return 9999
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

if st.button("🚀 Run Omni-Scraper"):
    
    with st.spinner("Fetching API Schedule..."):
        all_meetings = get_full_schedule()
        
    with st.spinner("Scraping Public Schedule (Checking Above & Below)..."):
        master_schedule = fetch_master_times()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7):
        week_map[today + timedelta(days=i)] = []
        
    valid_meetings = []
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            # --- THE MATCHING LOGIC ---
            api_time = m.get("ScheduleTime")
            api_comments = m.get("Comments") or ""
            
            final_time = api_time
            
            # 1. Trust API Comments first (e.g. "Upon Adjournment")
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            # 2. If API is bad, check Scraper
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                api_words = get_significant_words(name)
                
                if m_date in master_schedule:
                    best_match = None
                    max_overlap = 0
                    
                    for candidate in master_schedule[m_date]:
                        scraped_words = candidate['words']
                        overlap = len(api_words.intersection(scraped_words))
                        
                        # Strict Match: Need 2+ words (or 1 if unique)
                        if overlap > max_overlap:
                            max_overlap = overlap
                            best_match = candidate['time']
                    
                    if best_match and max_overlap >= 1:
                        final_time = best_match

            # 3. Fallback
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
                
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings:
        m['Bills'] = bill_results.get(m['ScheduleID'], [])

    cols = st.columns(7)
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
                    bill_count = len(m.get('Bills', []))
                    full_name = m.get("OwnerName", "")
                    parent_name, sub_name = parse_committee_name(full_name)
                    
                    time_str = m['DisplayTime']
                    is_long_text = len(time_str) > 15
                    
                    with st.container(border=True):
                        if is_long_text: st.caption(f"🕒 *{time_str}*") 
                        else: st.markdown(f"**{time_str}**")
                        
                        st.markdown(f"**{parent_name}**")
                        if sub_name: st.caption(f"↳ *{sub_name}*")
                        
                        if bill_count > 0:
                            st.success(f"**{bill_count} Bills Listed**")
                            with st.expander("View Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
