import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v20 Hybrid Master", page_icon="🏛️", layout="wide")
st.title("🏛️ v20: The Hybrid Master (API + Scraper)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: NORMALIZATION ---
def normalize_name(name):
    """Turns 'House Appropriations - Higher Ed' into 'appropriationshighered' for matching"""
    if not name: return ""
    return re.sub(r'[^a-zA-Z]', '', name.lower().replace("house", "").replace("senate", "").replace("committee", "").replace("subcommittee", ""))

# --- COMPONENT 1: THE MASTER TIME SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_master_times():
    """Scrapes the public schedule pages to find the 'True Times' for every committee"""
    time_map = {} # {'2026-01-21': {'appropriations': 'After Adjournment'}}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Scrape HOUSE Schedule
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        current_date = None
        rows = soup.find_all(['h4', 'div'], class_=['media-heading', 'meeting-time', 'meeting-committee'])
        
        # This scraper logic mimics your original app's reliable time finder
        text_blob = soup.get_text("\n")
        lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        for i, line in enumerate(lines):
            # Detect Date Header
            if "Monday," in line or "Tuesday," in line or "Wednesday," in line or "Thursday," in line or "Friday," in line:
                try:
                    # Parse "Wednesday, January 21, 2026"
                    clean_date = line.split(", ")[1] + " 2026" # e.g. January 21 2026
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                except: pass
            
            # Detect Time/Committee Pair
            if current_date:
                # Look for time patterns (9:00 AM, Upon Adjournment, etc)
                if any(x in line.lower() for x in ["am", "pm", "adjournment", "recess", "noon"]):
                    # The NEXT line is usually the committee name
                    time_val = line
                    if i + 1 < len(lines):
                        comm_name = lines[i+1]
                        norm_name = normalize_name(comm_name)
                        
                        if current_date not in time_map: time_map[current_date] = {}
                        time_map[current_date][norm_name] = time_val
    except: pass
    
    return time_map

# --- COMPONENT 2: THE API FETCH (Source A) ---
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
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        
        # Natural Sort
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

if st.button("🚀 Run Hybrid Forecast"):
    
    # 1. FETCH API DATA (Bills + Structure)
    with st.spinner("Fetching API Schedule..."):
        all_meetings = get_full_schedule()
        
    # 2. FETCH SCRAPER DATA (True Times)
    with st.spinner("Scraping Public Schedule for 'True Times'..."):
        master_time_map = fetch_times() # <--- ERROR in variable name fixed below, should be fetch_master_times()
        master_time_map = fetch_master_times()
        
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
            
            # --- THE MAGIC MERGE ---
            # 1. Start with API Time
            api_time = m.get("ScheduleTime")
            final_time = api_time
            
            # 2. If API is bad (TBA or 12:00 PM), try the Master Scraper Map
            if not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                norm_name = normalize_name(name)
                # Look for this committee on this date in the scraped map
                if m_date in master_time_map:
                    # Try to find a partial match
                    for scraped_name, scraped_time in master_time_map[m_date].items():
                        if scraped_name in norm_name or norm_name in scraped_name:
                            final_time = scraped_time # OVERWRITE WITH SCRAPED TIME
                            break
                            
            # 3. Final fallback
            if not final_time or final_time == "12:00 PM": 
                final_time = "Time TBA"
                
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    # 3. SCAN AGENDA PAGES FOR BILLS
    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas for bills..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings:
        m['Bills'] = bill_results.get(m['ScheduleID'], [])

    # 4. RENDER
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
