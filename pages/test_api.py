import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# --- CONFIGURATION ---
CGI_BASE = "https://lis.virginia.gov/cgi-bin/legp604.exe"
SESSION_CODE = "20261" # THE PROVEN KEY

st.set_page_config(page_title="v2900 Agenda Scraper", page_icon="🗓️", layout="wide")
st.title("🗓️ v2900: The 'Agenda' Scraper")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html'
}

def get_agenda():
    st.subheader(f"Step 1: Accessing Session {SESSION_CODE} Menu...")
    
    # 1. We start at the Session Menu to find the "Meetings" link
    # Usually ?20261+men+BIL is bills, ?20261+home is home
    start_url = f"{CGI_BASE}?{SESSION_CODE}+home"
    
    try:
        r = session.get(start_url, headers=headers, timeout=5)
        if r.status_code != 200:
            st.error("❌ Failed to load Session Home.")
            return

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 2. Find the "Meetings" or "Schedule" link
        meeting_link = None
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).lower()
            if "meetings" in text or "schedule" in text or "docket" in text:
                meeting_link = a['href']
                st.success(f"✅ Found Schedule Link: {text.title()}")
                break
        
        # Fallback: If we can't find the link, try the standard "Meetings" code (+men+MTG)
        if not meeting_link:
            st.warning("⚠️ link not found on home page. Trying direct 'Meetings Menu' code...")
            meeting_link = f"?{SESSION_CODE}+men+MTG"

        # 3. Load the Schedule Page
        # Ensure full URL
        if not meeting_link.startswith("http"):
            # Handle relative paths like ?20261+...
            if not meeting_link.startswith("/"):
                meeting_link = f"{CGI_BASE}{meeting_link}"
            else:
                 meeting_link = f"https://lis.virginia.gov{meeting_link}"
                 
        st.write(f"fetching Schedule: `{meeting_link}`")
        
        r2 = session.get(meeting_link, headers=headers, timeout=5)
        if r2.status_code == 200:
            # 4. PARSE THE MEETINGS
            # The structure is usually a <ul> or a <table> with dates and links
            soup2 = BeautifulSoup(r2.text, 'html.parser')
            text_dump = soup2.get_text("\n", strip=True)
            
            # Simple Text Extraction first (to ensure we see data)
            st.divider()
            st.subheader("📅 Upcoming Agendas Found")
            
            # We look for lines that look like dates or times
            relevant_lines = []
            capture = False
            
            # This is a basic parser - we can refine it once we see the format
            for line in text_dump.splitlines():
                # Filter out navigation junk
                if "Session" in line and "Home" in line: continue
                if "Help" in line: continue
                
                # Check for Days of Week (Strong signal for agenda)
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                if any(d in line for d in days):
                    relevant_lines.append(f"**{line}**") # Bold dates
                elif "AM" in line or "PM" in line:
                    relevant_lines.append(f"⏰ {line}")   # Formatting for times
                elif "Committee" in line:
                    relevant_lines.append(f"🏛️ {line}")   # Formatting for committees
                    
            if relevant_lines:
                for l in relevant_lines:
                    st.markdown(l)
            else:
                st.warning("Page loaded, but regex couldn't parse the layout. Viewing raw text below:")
                st.text_area("Raw Page Text", text_dump, height=400)
                
        else:
            st.error("❌ Failed to load Schedule Page.")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Fetch Agendas"):
    get_agenda()
