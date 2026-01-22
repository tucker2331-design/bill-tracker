import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v14 Nitro Forecast", page_icon="🔥", layout="wide")
st.title("🔥 v14: The Nitro Forecast (Unfiltered)")

# --- SPEED ENGINE: PERSISTENT SESSION ---
# This keeps the connection open so we don't handshake 20 times
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- CACHED SCHEDULE FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    all_items = []
    
    # We can even parallelize the initial API calls
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
        for r in results: all_items.extend(r)
        
    return all_items

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
    """Worker function using the global SESSION for speed"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        # Use 'session.get' instead of 'requests.get'
        resp = session.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        return sorted(list(clean_bills))
    except: return []

# --- PARALLEL PROCESSOR (Max Power) ---
def fetch_bills_parallel(meetings_list):
    tasks = []
    for m in meetings_list:
        if m.get('AgendaLink'):
            tasks.append((m, m['AgendaLink']))
            
    results = {}
    
    # Increased workers to 20 for maximum throughput
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_id = {executor.submit(scan_agenda_page, url): m['ScheduleID'] for m, url in tasks}
        
        for future in concurrent.futures.as_completed(future_to_id):
            mid = future_to_id[future]
            try:
                results[mid] = future.result()
            except:
                results[mid] = []
    return results

# --- MAIN UI ---

if st.button("🚀 Run Nitro Scan"):
    
    # 1. FETCH SCHEDULE
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        
    # 2. FILTER DATES
    today = datetime.now().date()
    week_map = {}
    for i in range(7):
        week_map[today + timedelta(days=i)] = []
        
    valid_meetings = []
    
    # Pre-process list
    for m in all_meetings:
        raw = m.get("ScheduleDate", "").split("T")[0]
        if not raw: continue
        m_date = datetime.strptime(raw, "%Y-%m-%d").date()
        
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            valid_meetings.append(m)
            week_map[m_date].append(m)

    # 3. PARALLEL SCAN
    # No progress bar this time - purely optimized for speed
    with st.spinner(f"🔥 Blasting {len(valid_meetings)} agendas..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    # Merge results
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
            # Sort by time
            daily_meetings.sort(key=lambda x: x.get("ScheduleTime", "0"))
            
            if not daily_meetings:
                st.info("No Committees")
            else:
                for m in daily_meetings:
                    # Determine Card Color based on bill count
                    bill_count = len(m.get('Bills', []))
                    
                    with st.container(border=True):
                        st.markdown(f"**{m.get('ScheduleTime')}**")
                        short_name = m.get("OwnerName", "").replace("Committee", "").replace("House", "H.").replace("Senate", "S.")
                        st.caption(short_name[:40])
                        
                        if bill_count > 0:
                            # Show bill count badge
                            st.success(f"**{bill_count} Bills Listed**")
                            # Expandable list so it doesn't clutter the view
                            with st.expander("See Bills"):
                                st.write(", ".join(m['Bills']))
                        elif m['AgendaLink']:
                            st.caption("*(Link found, 0 bills)*")
                        else:
                            st.caption("*(No Link)*")
