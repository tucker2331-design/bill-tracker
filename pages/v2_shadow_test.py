import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v24 Sniper Scraper", page_icon="🎯", layout="wide")
st.title("🎯 v24: The 'Sniper' Scraper")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT NORMALIZATION ---
def get_clean_tokens(text):
    """Turns 'House General Laws - Professions' into {'general', 'laws', 'professions'}"""
    if not text: return set()
    # Words to ignore to prevent false positives
    noise = {"house", "senate", "committee", "subcommittee", "room", "building", "meeting", "the", "of", "and", "&", "-", "agenda", "view", "video", "signup", "speak", "public", "testimony"}
    words = set(re.sub(r'[^a-zA-Z\s]', '', text.lower()).split())
    return words - noise

# --- COMPONENT 1: THE SCRAPER (Source B) ---
@st.cache_data(ttl=300)
def fetch_master_times():
    """
    Returns a dictionary: { Date: [ {text: "Full line text", tokens: {set of words}} ] }
    """
    schedule_map = {} 
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = session.get(url, headers=headers, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        current_date = None
        # Get all text elements
        all_tags = soup.find_all(['div', 'span', 'p', 'h4'])
        
        for tag in all_tags:
            text = tag.get_text(" ", strip=True)
            if not text: continue
            
            # 1. Detect Date Change
            if any(day in text for day in ["Monday,", "Tuesday,", "Wednesday,", "Thursday,", "Friday,"]):
                try:
                    # "Wednesday, January 21, 2026"
                    clean_date = text.split(", ")[1] + " 2026"
                    dt = datetime.strptime(clean_date, "%B %d %Y")
                    current_date = dt.date()
                except: pass
                continue
            
            # 2. Store Content
            if current_date:
                # We store EVERY meaningful line for this date
                if len(text) > 10:
                    if current_date not in schedule_map: schedule_map[current_date] = []
                    schedule_map[current_date].append({
                        "text": text,
                        "tokens": get_clean_tokens(text)
                    })
                    
    except Exception as e: pass
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
        if any(x in link.get_text().lower() for x in ["agenda", "committee info", "docket"]):
            return f"https://house.vga.virginia.gov{href}" if href.startswith("/") else href
    return None

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills: clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
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
    # Push Adjournment times to end of day (4:00 PM equivalent)
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

if st.button("🚀 Run Sniper Forecast"):
    
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        master_scraped_data = fetch_master_times()
        
    today = datetime.now().date()
    week_map = {}
    for i in range(7): week_map[today + timedelta(days=i)] = []
    valid_meetings = []
    
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            # --- THE SNIPER LOGIC ---
            api_time = m.get("ScheduleTime")
            api_comments = m.get("Comments") or ""
            
            final_time = api_time
            
            # 1. Trust API Comments first
            if "adjourn" in api_comments.lower() or "upon" in api_comments.lower():
                final_time = api_comments
                
            # 2. If API is vague, HUNT in the scraped data
            elif not api_time or "12:00" in str(api_time) or "TBA" in str(api_time):
                
                # Get tokens for this committee (e.g. {general, laws})
                target_tokens = get_clean_tokens(name)
                
                if m_date in master_scraped_data:
                    candidates = master_scraped_data[m_date]
                    
                    # Find the BEST matching line in the scraped text
                    best_line = None
                    max_score = 0
                    
                    for line_obj in candidates:
                        line_tokens = line_obj['tokens']
                        line_text = line_obj['text'].lower()
                        
                        # Calculate Overlap Score
                        overlap = len(target_tokens.intersection(line_tokens))
                        
                        # Only consider lines that ALSO have time info
                        has_time_info = any(x in line_text for x in ["adjournment", "recess", "upon", "after", "immediately", "am", "pm"])
                        
                        if overlap > max_score and has_time_info:
                            max_score = overlap
                            best_line = line_obj['text']
                            
                    # If we found a line with High Confidence (2+ matching words + time info)
                    if best_line and max_score >= 1:
                        # Extract the time phrase from the line (simplified: just use the line)
                        # Often the line IS the time: "1/2 hour after adjournment..."
                        final_time = best_line

            # 3. Fallback
            if not final_time or final_time == "12:00 PM": final_time = "Time TBA"
                
            m['DisplayTime'] = final_time
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            valid_meetings.append(m)
            week_map[m_date].append(m)

    with st.spinner(f"🔥 Scanning {len(valid_meetings)} agendas..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    for m in valid_meetings: m['Bills'] = bill_results.get(m['ScheduleID'], [])

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
                    # Clean up really long scraped lines
                    if len(time_str) > 50: time_str = "See Details (Complex Time)"
                    
                    with st.container(border=True):
                        if len(time_str) > 15: st.caption(f"🕒 *{time_str}*") 
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
