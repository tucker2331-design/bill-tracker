import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v19 True Time", page_icon="🕰️", layout="wide")
st.title("🕰️ v19: The 'True Time' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: NATURAL SORTING ---
def natural_sort_key(s):
    parts = re.match(r"([A-Za-z]+)(\d+)", s)
    if parts: return parts.group(1), int(parts.group(2))
    return s, 0

# --- HELPER: SMART TIME PARSER ---
def parse_time_rank(time_str):
    """
    Sorts meetings logically:
    1. Specific Times (8:00 AM) -> 0-899
    2. 'After Adjournment' -> 960 (4:00 PM approx)
    3. TBA -> 9999
    """
    if not time_str: return 9999
    clean = time_str.lower().replace(".", "").strip()
    
    # Priority for "Adjournment" (Push to afternoon)
    if "adjourn" in clean or "recess" in clean or "upon" in clean or "after" in clean:
        return 960 
            
    if "tba" in clean: return 9999
        
    try:
        dt = datetime.strptime(clean, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except:
        return 9999 

# --- HELPER: TEXT CLEANER ---
def clean_scraped_time(text):
    """Cleans up the raw scraped line"""
    # Remove "Time:" prefix if exists
    text = text.replace("Time:", "").strip()
    # Normalize spaces
    return " ".join(text.split())

# --- CORE FUNCTIONS ---
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
    seen_signatures = set()
    for m in raw_items:
        sig = (m.get('ScheduleDate'), m.get('ScheduleTime'), m.get('OwnerName'))
        if sig not in seen_signatures:
            seen_signatures.add(sig)
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
    """
    Scrapes BOTH the Bills AND the specific Meeting Time from the HTML
    """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text_content = soup.get_text()
        
        # 1. FIND BILLS
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text_content, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
            
        # 2. FIND TIME (The "True Time")
        # Look for specific phrases in the first 20 lines of the page
        scraped_time = None
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        
        # Heuristic: Scan top lines for time keywords
        for line in lines[:20]:
            lower_line = line.lower()
            if any(k in lower_line for k in ["adjournment", "recess", "upon", "immediately", "1/2 hour after"]):
                # Found a relative time! (e.g. "1/2 hour after adjournment")
                scraped_time = line
                break
            if "time:" in lower_line:
                scraped_time = line
                break
                
        return {
            "bills": sorted(list(clean_bills), key=natural_sort_key),
            "scraped_time": clean_scraped_time(scraped_time) if scraped_time else None
        }
    except: 
        return {"bills": [], "scraped_time": None}

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
            except: results[mid] = {"bills": [], "scraped_time": None}
    return results

def parse_committee_name(full_name):
    if " - " in full_name:
        parts = full_name.split(" - ", 1)
        return parts[0], parts[1]
    elif "Subcommittee" in full_name:
        return full_name, None
    return full_name, None

# --- MAIN UI ---

if st.button("🚀 Run Forecast"):
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        
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
            
            # Initial Time Guess (From API)
            api_time = m.get("ScheduleTime")
            if not api_time or api_time == "12:00 PM":
                api_time = "Time TBA" # Treat 12:00 PM default as TBA initially
                
            m['DisplayTime'] = api_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas (Bills + Times)..."):
        scan_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings:
        result = scan_results.get(m['ScheduleID'], {})
        m['Bills'] = result.get('bills', [])
        
        # --- THE TIME OVERRIDE ---
        # If the scraper found a specific time string (e.g. "1/2 hour after..."), use it!
        found_time = result.get('scraped_time')
        if found_time:
             # If API said 12:00 PM or TBA, definitively overwrite it
             if m['DisplayTime'] == "Time TBA" or "12:00" in m['DisplayTime']:
                 m['DisplayTime'] = found_time
             # Even if API had a time, prefer the "After Adjournment" text if found
             elif "adjourn" in found_time.lower():
                 m['DisplayTime'] = found_time

    cols = st.columns(7)
    days = sorted(week_map.keys())
    
    for i, day in enumerate(days):
        with cols[i]:
            st.markdown(f"### {day.strftime('%a')}")
            st.caption(day.strftime('%b %d'))
            st.divider()
            
            daily_meetings = week_map[day]
            
            # Sort: Fixed Times -> Floor Adj -> Comm Adj -> TBA
            daily_meetings.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            if not daily_meetings:
                st.info("No Committees")
            else:
                for m in daily_meetings:
                    bill_count = len(m.get('Bills', []))
                    full_name = m.get("OwnerName", "")
                    parent_name, sub_name = parse_committee_name(full_name)
                    
                    time_str = m['DisplayTime']
                    # Visual Cleanup
                    is_long_text = len(time_str) > 15
                    
                    with st.container(border=True):
                        if is_long_text:
                            st.caption(f"🕒 *{time_str}*") 
                        else:
                            st.markdown(f"**{time_str}**")
                        
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
