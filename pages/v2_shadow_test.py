import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v10 Horizontal Calendar", page_icon="🗓️", layout="wide")
st.title("🗓️ v10: The Weekly Horizontal Forecast")

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
    """Converts '9:00 AM' into a sortable number"""
    if not time_str: return 9999 # Put unknowns at the end
    try:
        # Remove dots (a.m. -> am) and whitespace
        clean = time_str.lower().replace(".", "").strip()
        dt = datetime.strptime(clean, "%I:%M %p")
        return dt.hour * 60 + dt.minute
    except:
        return 9999

# --- MAIN UI ---

if st.button("🚀 Generate Weekly Calendar"):
    with st.spinner("Building Calendar..."):
        all_meetings = get_full_schedule()
        
    # 1. SETUP THE 7-DAY BUCKETS
    today = datetime.now().date()
    # Create a dictionary for the next 7 days: { "2026-01-21": [], "2026-01-22": [] ... }
    week_map = {}
    for i in range(7):
        day = today + timedelta(days=i)
        week_map[day] = [] # Initialize empty list for every day
        
    # 2. FILL BUCKETS
    for m in all_meetings:
        raw_date = m.get("ScheduleDate", "").split("T")[0]
        if not raw_date: continue
        m_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        
        # Only add if it falls in our 7-day window
        if m_date in week_map:
            name = m.get("OwnerName", "")
            # Skip noise
            if "Caucus" in name or "Press" in name: continue
            
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            week_map[m_date].append(m)

    # 3. RENDER HORIZONTALLY
    # Create 7 columns
    cols = st.columns(7)
    
    # Loop through the days sorted (Today -> +6 days)
    sorted_days = sorted(week_map.keys())
    
    for i, day in enumerate(sorted_days):
        col = cols[i]
        daily_meetings = week_map[day]
        
        # SORT BY TIME (e.g. 7:30 AM before 9:00 AM)
        daily_meetings.sort(key=lambda x: parse_time_for_sort(x.get("ScheduleTime")))
        
        with col:
            # Header: "Wed 21"
            st.markdown(f"### {day.strftime('%a')}")
            st.caption(day.strftime('%b %d'))
            st.divider()
            
            if not daily_meetings:
                st.markdown("*No Meetings*")
            else:
                for m in daily_meetings:
                    # Unique Key for Buttons
                    btn_key = f"{m.get('ScheduleID')}_{i}"
                    
                    with st.container(border=True):
                        st.markdown(f"**{m.get('ScheduleTime')}**")
                        # Shorten huge names (e.g. "House Agriculture..." -> "House Ag...")
                        short_name = m.get("OwnerName", "").replace("Committee", "").replace("House", "H.").replace("Senate", "S.")
                        st.caption(short_name[:40]) # Cut off if too long
                        
                        if m['AgendaLink']:
                            if st.button("Bills?", key=btn_key):
                                bills = scan_agenda_page(m['AgendaLink'])
                                if bills:
                                    st.toast(f"Found: {', '.join(bills)}", icon="✅")
                                else:
                                    st.toast("Empty Agenda", icon="⚠️")
                        else:
                            st.caption("No Link")
