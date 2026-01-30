import streamlit as st
import requests
import re

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
CGI_BASE = "https://lis.virginia.gov/cgi-bin/legp604.exe"
SESSION_CODE = "20261" # For API
SESSION_CGI = "261"    # For Website (2026 Regular)
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v2200 Hybrid Tracker", page_icon="🧬", layout="wide")
st.title("🧬 v2200: The 'Hybrid' Tracker")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

# --- PART 1: THE WORKING API (METADATA) ---
def fetch_bill_metadata(bill_num):
    url = f"{API_BASE}/LegislationVersion/api/GetLegislationVersionByBillNumberAsync"
    params = {"sessionCode": SESSION_CODE, "billNumber": bill_num}
    
    try:
        r = session.get(url, headers=headers, params=params, timeout=2)
        if r.status_code == 200:
            data = r.json()
            items = []
            if isinstance(data, dict): items = data.get("LegislationsVersion", [])
            elif isinstance(data, list): items = data
            
            if items:
                # Return the most recent version info
                latest = items[0]
                return {
                    "Bill": bill_num,
                    "ID": latest.get("LegislationID"),
                    "Title": latest.get("Description"), # Usually "Introduced"
                    "Date": latest.get("DraftDate"),
                    "Found": True
                }
    except:
        pass
    return None

# --- PART 2: THE WEBSITE SCRAPER (COMMITTEE) ---
def fetch_bill_committee_html(bill_num):
    # Construct the URL for the Bill Summary Page
    # Format: ?261+sum+HB1
    url = f"{CGI_BASE}?{SESSION_CGI}+sum+{bill_num}"
    
    try:
        # We need standard browser headers for the CGI to talk to us
        scrape_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html'
        }
        r = session.get(url, headers=scrape_headers, timeout=3)
        
        if r.status_code == 200:
            html = r.text
            
            # 1. Look for "Referred to Committee" pattern
            # The site usually says: "Referred to Committee on [Name]"
            match = re.search(r"Referred to Committee on ([A-Za-z\s]+)", html)
            if match:
                return match.group(1).strip()
            
            # 2. Look for "Referred to Committee" (Generic)
            if "Referred to Committee" in html:
                # Try to grab the text after it
                clean_text = re.sub(r'<[^>]+>', '', html) # Strip HTML tags
                idx = clean_text.find("Referred to Committee on")
                if idx != -1:
                    return clean_text[idx:idx+50] # Return snippet
                
            return "Not yet referred"
        else:
            return "HTML Fetch Failed"
    except Exception as e:
        return f"Error: {str(e)}"

# --- MAIN CONTROLLER ---
def run_hybrid_tracker():
    st.subheader(f"Step 1: Tracking HB1 - HB10 (Session {SESSION_CODE})")
    
    results = []
    
    # Create a progress bar
    progress = st.progress(0)
    status_text = st.empty()
    
    for i in range(1, 11): # Check first 10 bills
        b_num = f"HB{i}"
        status_text.text(f"Scanning {b_num}...")
        
        # 1. API CALL (Fast, clean)
        meta = fetch_bill_metadata(b_num)
        
        if meta:
            # 2. SCRAPE CALL (Slower, but has the data)
            committee = fetch_bill_committee_html(b_num)
            
            # Combine
            meta["Committee (Scraped)"] = committee
            results.append(meta)
            
        progress.progress(i * 10)
        
    status_text.text("Scan Complete.")
    
    if results:
        st.success(f"🎉 **SUCCESS!** Tracked {len(results)} bills.")
        
        # Display as a clean table
        st.dataframe(results, column_order=["Bill", "Committee (Scraped)", "Title", "Date", "ID"])
        
        # Transparency: Show the raw source for HB1
        st.divider()
        st.subheader("🔎 Transparency: Source Data for HB1")
        
        c1, c2 = st.columns(2)
        with c1:
            st.info("API (JSON) Return")
            st.json(fetch_bill_metadata("HB1"))
        with c2:
            st.warning("Website (HTML) Scrape")
            url = f"{CGI_BASE}?{SESSION_CGI}+sum+HB1"
            st.write(f"Scraped URL: `{url}`")
            comm = fetch_bill_committee_html("HB1")
            st.metric("Extracted Committee", comm)

    else:
        st.error("❌ No bills found via API. (Is the Session Code correct?)")

if st.button("🔴 Run Hybrid Tracker"):
    run_hybrid_tracker()
