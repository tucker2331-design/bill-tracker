import streamlit as st
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v4 Agenda Crawler", page_icon="🕷️", layout="wide")
st.title("🕷️ v4: The Agenda Crawler")

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
    """Step 2: Find the 'Agenda' link inside the messy description"""
    if not html_string: return None
    # Look for the pattern href="..."
    soup = BeautifulSoup(html_string, 'html.parser')
    for link in soup.find_all('a'):
        href = link.get('href')
        text = link.get_text().lower()
        # We want the link that says 'Agenda'
        if "agenda" in text and href:
            # Fix relative links if necessary
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
        
        # Regex to find bills (e.g., HB1, SB 50, H.B. 100)
        # Matches: (HB or SB or HJ or SJ) followed by optional spaces/dots, then numbers
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?|H\.?R\.?|S\.?R\.?)\s*(\d+)', text_content, re.IGNORECASE)
        
        # Clean up the results
        clean_bills = set()
        for prefix, number in bills:
            clean_prefix = prefix.upper().replace(".","").strip()
            clean_bills.add(f"{clean_prefix}{number}")
            
        return list(clean_bills)
    except Exception as e:
        return []

# --- MAIN UI ---

if st.button("🚀 Run Crawler (Today's Meetings)"):
    
    # 1. Get House Meetings
    with st.spinner("Talking to API..."):
        meetings = get_schedule_from_api("H")
        
    today_str = datetime.now().strftime("%Y-%m-%d")
    found_count = 0
    
    for m in meetings:
        raw_date = m.get("ScheduleDate", "")
        
        # Filter for TODAY (or recent/future)
        if raw_date.startswith(today_str):
            found_count += 1
            name = m.get("OwnerName", "Unknown Committee")
            desc_html = m.get("Description", "")
            
            st.markdown(f"### 🏛️ {name}")
            st.caption(f"Time: {m.get('ScheduleTime')}")
            
            # 2. Extract Link
            target_url = extract_url_from_html(desc_html)
            
            if target_url:
                st.success(f"🔗 Found Agenda Link: {target_url}")
                
                # 3. Scan It
                with st.spinner("Scanning Agenda Page..."):
                    found_bills = scan_agenda_page(target_url)
                    
                if found_bills:
                    st.balloons()
                    st.warning(f"🚨 FOUND {len(found_bills)} BILLS ON AGENDA!")
                    st.write(found_bills)
                else:
                    st.info("Link found, but no bills detected on page.")
            else:
                st.error("No 'Agenda' link found in API description.")
                with st.expander("See Raw Description"):
                    st.code(desc_html)
            
            st.divider()
            
    if found_count == 0:
        st.warning(f"No meetings found in API for today ({today_str}).")
