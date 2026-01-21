import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures # <-- THE SPEED ENGINE

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

# 🎯 YOUR WATCHLIST (In the real app, this comes from your Google Sheet)
# This mimics "only checking for bills we have"
MY_WATCHLIST = ["HB1", "HB104", "HB270", "SB5", "HB397"] 

st.set_page_config(page_title="v13 Turbo Forecast", page_icon="🏎️", layout="wide")
st.title("🏎️ v13: The Turbo Forecast")

# --- CACHED FUNCTIONS (Speed Layer 1) ---

@st.cache_data(ttl=900) # Cache for 15 minutes
def get_full_schedule():
    """Gets the Master Schedule (Fast)"""
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    all_items = []
    for chamber in ["H", "S"]:
        try:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = requests.get(url, headers=headers, params=params, timeout=5)
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
        if any(x in text for x in ["agenda", "committee info", "docket"]):
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    """The Worker Function"""
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

# --- PARALLEL PROCESSOR (Speed Layer 2) ---
def fetch_bills_parallel(meetings_list):
    """Scans all URLs at the same time using threads"""
    
    # Identify which meetings actually have links
    tasks = []
    for m in meetings_list:
        if m.get('AgendaLink'):
            tasks.append((m, m['AgendaLink']))
            
    results = {}
    
    # Run 10 requests at once
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Create a dictionary of {Future: Meeting}
        future_to_meeting = {executor.submit(scan_agenda_page, url): m for m, url in tasks}
        
        for future in concurrent.futures.as_completed(future_to_meeting):
            meeting = future_to_meeting[future]
            try:
                bills = future.result()
                results[meeting['ScheduleID']] = bills
            except:
                results[meeting['ScheduleID']] = []
                
    return results

# --- MAIN UI ---

if st.button("🚀 Run Turbo Scan"):
    
    # 1. GET SCHEDULE (Cached)
    with st.spinner("Fetching Schedule..."):
        all_meetings = get_full_schedule()
        
    # 2. FILTER DATES
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
            
            m['CleanDate'] = m_date
            m['AgendaLink'] = extract_agenda_link(m.get("Description"))
            valid_meetings.append(m)
            week_map[m_date].append(m)

    # 3. PARALLEL SCAN (The Fast Part)
    with st.spinner(f"⚡ Scanning {len(valid_meetings)} agendas in parallel..."):
        bill_results = fetch_bills_parallel(valid_meetings)
        
    # Merge results back into objects
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
            
            if not daily_meetings:
                st.info("No Committees")
            else:
                for m in daily_meetings:
                    # CHECK FOR OUR BILLS
                    my_bills_found = [b for b in m.get('Bills', []) if b in MY_WATCHLIST]
                    has_my_bills = len(my_bills_found) > 0
                    
                    # CARD STYLE: Highlight if it has our bills
                    border_color = "red" if has_my_bills else None
                    
                    with st.container(border=True):
                        if has_my_bills:
                            st.error(f"🚨 **{len(my_bills_found)} WATCHED BILLS!**")
                        
                        st.markdown(f"**{m.get('ScheduleTime')}**")
                        short_name = m.get("OwnerName", "").replace("Committee", "").replace("House", "H.").replace("Senate", "S.")
                        st.caption(short_name[:40])
                        
                        # Show Bills
                        if m.get('Bills'):
                            # Only show ALL bills if you want, otherwise just show ours?
                            # For now, listing all, highlighting ours
                            bill_badges = []
                            for b in m['Bills']:
                                if b in MY_WATCHLIST:
                                    bill_badges.append(f"**:red[{b}]**") # Highlight
                                else:
                                    bill_badges.append(b)
                            
                            st.markdown(", ".join(bill_badges))
                        elif m['AgendaLink']:
                            st.caption("*(0 bills)*")
                        else:
                            st.caption("*(No Link)*")
