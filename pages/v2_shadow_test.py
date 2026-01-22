import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v21 Fuzzy Hybrid", page_icon="🧬", layout="wide")
st.title("🧬 v21: The Fuzzy Hybrid (Smart Matching)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT NORMALIZATION ---
def get_significant_words(text):
    """Turns 'House General Laws - Professions' into {'general', 'laws', 'professions'}"""
    if not text: return set()
    # Remove standard noise words
    noise = {"house", "senate", "committee", "subcommittee", "room", "building", "meeting", "the", "of", "and", "&", "-"}
    # Clean and split
    words = set(re.sub(r'[^a-zA-Z\s]', '', text.lower()).split())
    # Return only meaningful words
    return words - noise

# --- COMPONENT 1: THE MASTER TIME SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_master_times():
    """Scrapes public schedule and returns a map of {Date: [{Words: set, Time: str}]}"""
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        current_date = None
        text_blob = soup.get_text("\n")
        lines = [x.strip() for x in text_blob.splitlines() if x.strip()]
        
        for i, line in enumerate(lines):
            # 1. Detect Date
            if "Monday," in line or "Tuesday," in line or "Wednesday," in line or "Thursday," in line or "Friday," in line:
                try:
                    clean_date = line.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                except: pass
            
            # 2. Detect Time + Committee
            if current_date:
                # Look for time signatures
                if any(x in line.lower() for x in ["am", "pm", "adjournment", "recess", "noon", "upon"]):
                    time_val = line
                    # The next line is usually the committee
                    if i + 1 < len(lines):
                        comm_name = lines[i+1]
                        
                        # Store as an object we can fuzzy match against later
                        if current_date not in schedule_map: schedule_map[current_date] = []
                        schedule_map[current_date].append({
                            "words": get_significant_words(comm_name),
                            "raw_name": comm_name,
                            "time": time_val
                        })
    except: pass
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

if st.button("🚀 Run Fuzzy Hybrid"):
    
    with st.spinner("Fetching API Schedule..."):
        all_meetings = get_full_schedule()
        
    with st.spinner("Scraping Public Schedule & Matching Times..."):
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
            
            # --- THE FUZZY MATCH LOGIC ---
            api_time = m.get("ScheduleTime")
            final_time = api_time
            
            # Only try to fix if API failed
            if not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                # Get the core words of this committee (e.g. {general, laws, professions})
                api_words = get_significant_words(name)
                
                if m_date in master_schedule:
                    # Look through all scraped meetings for this day
                    best_match = None
                    max_overlap = 0
                    
                    for candidate in master_schedule[m_date]:
                        scraped_words = candidate['words']
                        # Count overlap
                        overlap = len(api_words.intersection(scraped_words))
                        
                        # We need at least 2 words to match (or 1 if it's a very unique word)
                        # "Professions" + "Laws" = 2 matches -> High confidence
                        if overlap > max_overlap:
                            max_overlap = overlap
                            best_match = candidate['time']
                    
                    if best_match and max_overlap >= 1:
                        final_time = best_match

            # Fallback
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
