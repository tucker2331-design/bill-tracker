import streamlit as st
import requests
import json
import time
import io
# Try to import PDF reader, handle if missing
try:
    from pypdf import PdfReader
except ImportError:
    st.error("⚠️ Library Missing: Please add 'pypdf' to your requirements.txt file!")
    st.stop()

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v2 PDF Scanner", page_icon="📄", layout="wide")
st.title("📄 v2 Shadow Tracker (PDF Scanner)")

# --- FUNCTIONS ---
def fetch_api_calendar(chamber_code):
    """Gets the list of PDF links from the API"""
    url = "https://lis.virginia.gov/Calendar/api/getcalendarlistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": chamber_code}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200: return resp.json()
    except: pass
    return {}

def scan_pdf_for_bills(pdf_url):
    """Downloads a PDF and extracts all bill numbers (HB1, SB5, etc.)"""
    try:
        # 1. Download the PDF into memory
        response = requests.get(pdf_url, timeout=10)
        f = io.BytesIO(response.content)
        
        # 2. Read the Text
        reader = PdfReader(f)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
            
        return full_text
    except Exception as e:
        return f"Error reading PDF: {e}"

# --- MAIN UI ---
col1, col2 = st.columns(2)

# HOUSE SCANNER
with col1:
    st.subheader("🏛️ House Agendas")
    h_data = fetch_api_calendar("H")
    calendars = h_data.get("Calendars", [])
    
    if calendars:
        # Just grab the most recent calendar to test
        latest_day = calendars[0]
        date_str = latest_day.get("CalendarDate", "").split("T")[0]
        files = latest_day.get("CalendarFiles", [])
        
        st.info(f"📅 Examining Agenda for: **{date_str}**")
        
        if files:
            for f in files:
                url = f.get("FileURL")
                st.markdown(f"**Found PDF:** [Link]({url})")
                
                # THE MAGICAL BUTTON
                if st.button(f"🔍 Scan PDF #{f.get('CalendarFileID')}", key=f['CalendarFileID']):
                    with st.spinner("Downloading & Reading PDF..."):
                        text_content = scan_pdf_for_bills(url)
                        
                        # VISUALIZE RESULTS
                        st.success("✅ PDF Scanned Successfully!")
                        
                        # Simple Check for HB1
                        if "HB1" in text_content or "HB 1" in text_content:
                            st.balloons()
                            st.error("🚨 HB1 FOUND IN THIS PDF!")
                        else:
                            st.warning("HB1 NOT found in this text.")
                            
                        with st.expander("View Full PDF Text"):
                            st.text(text_content)
        else:
            st.caption("No PDF files attached to this date.")

# SENATE SCANNER
with col2:
    st.subheader("🏛️ Senate Agendas")
    s_data = fetch_api_calendar("S")
    calendars = s_data.get("Calendars", [])
    
    if calendars:
        latest_day = calendars[0]
        date_str = latest_day.get("CalendarDate", "").split("T")[0]
        files = latest_day.get("CalendarFiles", [])
        
        st.info(f"📅 Examining Agenda for: **{date_str}**")
        
        if files:
            for f in files:
                url = f.get("FileURL")
                if st.button(f"🔍 Scan PDF #{f.get('CalendarFileID')}", key=f['CalendarFileID']):
                    text_content = scan_pdf_for_bills(url)
                    with st.expander("View Full PDF Text"):
                        st.text(text_content)
