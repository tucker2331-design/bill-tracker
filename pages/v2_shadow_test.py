import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" # Strict String Match

st.set_page_config(page_title="v8 Forecast", page_icon="🔮", layout="wide")
st.title("🔮 v8: The Clean 7-Day Forecast")

# --- FUNCTIONS ---
def get_full_schedule():
    """Gets the MASTER list of all meetings"""
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    all_items = []
    # Fetch both chambers
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
    """Finds the hidden PDF/Page link"""
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text().lower()
        # Look for these specific link text patterns
        if any(x in text for x in ["agenda", "committee info", "docket", "meeting info"]):
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    """Visits the link and scrapes bill numbers"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text()
        # Find patterns like HB1, SB 50, H.B. 100
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean_bills = set()
        for p, n in bills:
            clean_bills.add(f"{p.upper().replace('.','').strip()}{n}")
        return sorted(list(clean_bills))
    except: return []

# --- MAIN UI ---

if st.button("🚀 Generate Forecast"):
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        
    # Setup Dates
    today = datetime.now().date()
    end_date = today + timedelta(days=14) # Look 2 weeks ahead
    
    future_meetings = []
    
    for m in all_meetings:
        # 1. PARSE DATE
        raw_date = m.get("ScheduleDate", "").split("T")[0]
        if not raw_date: continue
        m_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        
        # 2. FILTER: MUST be Today or Future (No 2022 stuff!)
        if today <= m_date <= end_date:
            
            # 3. FILTER: Must be a Committee (No Caucuses)
            name = m.get("OwnerName", "")
            sType = m.get("ScheduleType", "")
            
            # Skip Caucuses, Press Conferences, and empty placeholders
            if "Caucus" in name or "Press" in name:
                continue
                
            m['CleanDate'] = m_date
            
            # 4. PRE-CALCULATE LINK (Optimization)
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            
            future_meetings.append(m)

    # Sort chronological
    future_meetings.sort(key=lambda x: x['CleanDate'])
    
    if not future_meetings:
        st.warning("No Committee meetings found for the next 14 days.")
    else:
        st.success(f"Found {len(future_meetings)} Upcoming Committee Meetings")
        
        # GROUP BY DAY
        current_date = None
        for m in future_meetings:
            if m['CleanDate'] != current_date:
                current_date = m['CleanDate']
                st.markdown(f"### 🗓️ {current_date.strftime('%A, %b %d')}")
                st.divider()

            with st.container():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{m.get('OwnerName')}**")
                    st.caption(f"⏰ {m.get('ScheduleTime')} | 📍 {m.get('RoomDescription')}")
                
                with col2:
                    if m['AgendaLink']:
                        # THE "SCAN" BUTTON
                        if st.button(f"🔍 Scan Bills", key=m['ScheduleID']):
                            with st.spinner("Checking..."):
                                bills = scan_agenda_page(m['AgendaLink'])
                                if bills:
                                    st.success(f"Found {len(bills)} Bills!")
                                    st.code(", ".join(bills))
                                else:
                                    st.warning("Agenda page found, but no bills listed yet.")
                    else:
                        st.caption("No Agenda Link")
