import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v5 Week Crawler", page_icon="📅", layout="wide")
st.title("📅 v5: 7-Day Agenda Crawler")
st.caption("Scanning the next 7 days of Committee Agendas directly from the source.")

# --- FUNCTIONS ---

def get_schedule_from_api(chamber):
    """Step 1: Get the list of meetings from the API"""
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("Schedules", [])
    except: pass
    return []

def extract_url_from_html(html_string):
    """Step 2: Find the link. Enhanced to catch Senate 'Committee Info' links too."""
    if not html_string: return None
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text().lower()
        
        # KEYWORDS TO LOOK FOR
        valid_keywords = ["agenda", "committee info", "docket", "meeting info"]
        
        if any(word in text for word in valid_keywords) and href:
            if href.startswith("/"): return f"https://house.vga.virginia.gov{href}"
            return href
    return None

def scan_agenda_page(url):
    """Step 3: Visit the page and find bill numbers"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text_content = soup.get_text()
        
        # Regex to find bills (HB1, SB 50, etc.)
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?|H\.?R\.?|S\.?R\.?)\s*(\d+)', text_content, re.IGNORECASE)
        
        clean_bills = set()
        for prefix, number in bills:
            clean_prefix = prefix.upper().replace(".","").strip()
            clean_bills.add(f"{clean_prefix}{number}")
            
        return sorted(list(clean_bills))
    except:
        return []

# --- MAIN UI ---

if st.button("🚀 Scan Next 7 Days"):
    
    # 1. Fetch Data
    with st.spinner("Fetching Master Schedule..."):
        h_meetings = get_schedule_from_api("H")
        s_meetings = get_schedule_from_api("S")
        all_meetings = h_meetings + s_meetings
        
    # 2. Filter for Next 7 Days
    today = datetime.now()
    end_date = today + timedelta(days=7)
    
    # Bucket meetings by date strings (e.g., "2026-01-21")
    calendar_buckets = {}
    
    for m in all_meetings:
        raw_date_str = m.get("ScheduleDate", "").split("T")[0]
        if not raw_date_str: continue
        
        try:
            m_date = datetime.strptime(raw_date_str, "%Y-%m-%d")
            # Check if within range
            if today.date() <= m_date.date() <= end_date.date():
                if raw_date_str not in calendar_buckets:
                    calendar_buckets[raw_date_str] = []
                calendar_buckets[raw_date_str].append(m)
        except:
            continue

    # 3. Display Logic
    sorted_dates = sorted(calendar_buckets.keys())
    
    if not sorted_dates:
        st.warning("No meetings found for the next 7 days.")
    
    for date_str in sorted_dates:
        # Convert date to nice format (e.g. "Wednesday, Jan 21")
        nice_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %b %d")
        
        st.header(f"🗓️ {nice_date}")
        
        for m in calendar_buckets[date_str]:
            name = m.get("OwnerName", "Unknown Committee")
            time = m.get("ScheduleTime", "TBA")
            desc_html = m.get("Description", "")
            
            with st.expander(f"⏰ {time} - {name}"):
                # Find Link
                target_url = extract_url_from_html(desc_html)
                
                if target_url:
                    st.markdown(f"🔗 [View Original Agenda]({target_url})")
                    
                    # SCAN BUTTON (Manual trigger to save speed)
                    if st.button(f"🔍 Scan Bills for {name}", key=m.get('ScheduleID')):
                        with st.spinner("Reading Agenda..."):
                            found_bills = scan_agenda_page(target_url)
                            if found_bills:
                                st.success(f"Found {len(found_bills)} Bills:")
                                st.write(found_bills)
                            else:
                                st.warning("Link found, but no bills listed on page yet.")
                else:
                    st.info("No online agenda link posted yet.")
        
        st.divider()
