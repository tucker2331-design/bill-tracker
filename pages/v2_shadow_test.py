import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v11 Stable Calendar", page_icon="🗓️", layout="wide")
st.title("🗓️ v11: The Crash-Proof Weekly Forecast")

# --- FUNCTIONS ---
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    all_items = []
    for chamber in ["H", "S"]:
        try:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("Schedules", [])
                for item in data: item['Chamber'] = chamber
                all_items.extend(data)
        except: pass
    return all_items

def extract_agenda_link(html_string):
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text().lower()
        if any(x in text for x in ["agenda", "committee info", "docket", "meeting info"]):
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        return sorted(list(clean_bills))
    except: return []

def parse_time_for_sort(time_str):
    if not time_str: return 9999
    try:
        clean = time_str.lower().replace(".", "").strip()
        dt = datetime.strptime(clean, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except: return 9999

# --- MAIN UI ---

if st.button("🚀 Generate Weekly Calendar"):
    with st.spinner("Building Calendar..."):
        all_meetings = get_full_schedule()
        
    # 1. INITIALIZE 7-DAY BUCKETS (Empty slots for every day)
    today = datetime.now().date()
    week_map = {}
    for i in range(7):
        day = today + timedelta(days=i)
        week_map[day] = [] 
        
    # 2. FILL BUCKETS
    for m in all_meetings:
        raw_date = m.get("ScheduleDate", "").split("T")[0]
        if not raw_date: continue
        m_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        
        # Only add if it falls in our 7-day window
        if m_date in week_map:
            name = m.get("OwnerName", "")
            if "Caucus" in name or "Press" in name: continue
            
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            week_map[m_date].append(m)

    # 3. RENDER HORIZONTALLY
    cols = st.columns(7)
    sorted_days = sorted(week_map.keys())
    
    # Outer Loop: The 7 Days (Columns)
    for day_index, day in enumerate(sorted_days):
        col = cols[day_index]
        daily_meetings = week_map[day]
        
        # Sort Chronologically
        daily_meetings.sort(key=lambda x: parse_time_for_sort(x.get("ScheduleTime")))
        
        with col:
            st.markdown(f"### {day.strftime('%a')}")
            st.caption(day.strftime('%b %d'))
            st.divider()
            
            if not daily_meetings:
                st.info("No Committees")
            else:
                # Inner Loop: The Meetings within that day
                for meeting_index, m in enumerate(daily_meetings):
                    
                    # --- CRASH PROOF KEY ---
                    # Key is now: "ID" + "DayIndex" + "MeetingIndex"
                    # This guarantees it is unique even if the ID is duplicated
                    btn_key = f"btn_{m.get('ScheduleID')}_{day_index}_{meeting_index}"
                    
                    with st.container(border=True):
                        st.markdown(f"**{m.get('ScheduleTime')}**")
                        short_name = m.get("OwnerName", "").replace("Committee", "").replace("House", "H.").replace("Senate", "S.")
                        st.caption(short_name[:40])
                        
                        if m['AgendaLink']:
                            if st.button("Bills?", key=btn_key):
                                bills = scan_agenda_page(m['AgendaLink'])
                                if bills:
                                    st.success(f"{len(bills)} Bills")
                                    st.code(", ".join(bills))
                                else:
                                    st.warning("Empty Agenda")
                        else:
                            st.caption("No Link")
