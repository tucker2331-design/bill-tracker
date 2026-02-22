import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures
import time
from bs4 import BeautifulSoup
import pytz

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
SESSION_CODE = "20261"
MAX_CONCURRENT_SCRAPES = 3 

st.set_page_config(page_title="v93 Chrono Calendar", page_icon="📆", layout="wide")
st.title("📆 v93: Global API Calendar (Restored Fetch)")

est = pytz.timezone('US/Eastern')
if st.sidebar.button("🔄 Clear Cache & Refresh Live"):
    st.cache_data.clear()
    st.sidebar.success("Cache cleared! Pulling fresh LIS data.")

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: V90.1 PROVEN LINK EXTRACTOR ---
def extract_agenda_link(description_html):
    """Restored to the v90.1 logic that successfully pulled Senate URLs."""
    if not description_html: return None
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

# --- HELPER: REGEX DOCKET SCRAPER ---
def extract_bills_from_text(text_content):
    clean_bills = []
    pattern = r'\b([HS][BJR])\s*((?:\d+(?:[A-Z]\d+)?)(?:\s*(?:,|&|and)\s*\d+(?:[A-Z]\d+)?)*)\b'
    matches = re.finditer(pattern, text_content, re.IGNORECASE)
    
    for match in matches:
        prefix = match.group(1).upper()
        numbers_string = match.group(2)
        individual_numbers = re.split(r',|&|and', numbers_string)
        
        for num_str in individual_numbers:
            num_clean = num_str.strip().upper().replace(" ", "")
            if not num_clean: continue
                
            raw_bill = f"{prefix}{num_clean}"
            sanitized_bill = re.sub(r'^([A-Z]+)0+(\d+.*)$', r'\1\2', raw_bill)
            
            if sanitized_bill not in clean_bills:
                clean_bills.append(sanitized_bill)
    return clean_bills

def scrape_docket_for_bills(link_url):
    if not link_url: return []
    if any(ext in str(link_url).lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]):
        return ["DOCUMENT_DETECTED"]
        
    try:
        time.sleep(0.1) 
        resp = session.get(link_url, timeout=5)
        if resp.status_code != 200: return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        text_content = soup.get_text(" ", strip=True)
        return extract_bills_from_text(text_content)
    except Exception:
        return []

# --- API FETCH: RESTORED V90.1 MASS FETCH ---
@st.cache_data(ttl=600)
def get_global_schedule_grid():
    """Restored to massive one-time fetch, bypassing broken LIS date filters."""
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: 
                h_data = h.result().json()
                raw_items.extend(h_data.get("Schedules", h_data.get("ListItems", [])))
            if s.result().status_code == 200: 
                s_data = s.result().json()
                raw_items.extend(s_data.get("Schedules", s_data.get("ListItems", [])))
            
        return raw_items
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

# --- SORTING LOGIC (V92 FORMATTING) ---
def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = str(time_str).upper().replace(".", "")
    if "CANCEL" in t_upper or "WILL NOT MEET" in t_upper: return 8888
    if "ADJOURN" in t_upper or "UPON" in t_upper or "RISE" in t_upper or "AFTER" in t_upper: return 2000 
    
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

def strip_html_tags(text):
    """Prevents raw HTML from rendering in the UI for relational times."""
    if not text: return ""
    return BeautifulSoup(str(text), "html.parser").get_text(" ", strip=True)

# --- MAIN ENGINE EXECUTION ---
with st.spinner("Step 1: Fetching API Master Grid..."):
    all_raw_items = get_global_schedule_grid()

processed_events = []
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    date_obj = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if date_obj < datetime.now(est).date(): continue # Drop past days
    if date_obj > datetime.now(est).date() + timedelta(days=7): continue # Cap at 7 days out
    
    name = str(m.get("OwnerName", "")).strip()
    sched_time = str(m.get("ScheduleTime", "")).strip()
    
    # Deduplication
    sig = (raw_date, sched_time, name)
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = date_obj
    clean_name = name.replace("Virginia ", "").replace(" of Delegates", "").strip()
    m['IsFloor'] = bool(re.match(r'^(House|Senate)(?:\s+Convenes|\s+Session)?$', clean_name, re.IGNORECASE))
    m['IsCaucus'] = any(x in clean_name.upper() for x in ["CAUCUS", "DELEGATION", "PRAYER", "BIBLE STUDY"])
    
    # Relational Time & Clean HTML Format
    comm = str(m.get("Comments", "")).strip()
    desc = str(m.get("Description", "")).strip()
    
    if sched_time:
        m['DisplayTime'] = sched_time
    elif comm and any(x in comm.lower() for x in ["adjourn", "upon", "rise", "after"]): 
        m['DisplayTime'] = strip_html_tags(comm)
    elif desc and any(x in desc.lower() for x in ["adjourn", "upon", "rise", "after"]): 
        m['DisplayTime'] = strip_html_tags(desc)
    else: 
        m['DisplayTime'] = "Time TBA"
        
    # Cancellation Logic
    is_cancelled_db = m.get("IsCancelled") is True
    is_will_not_meet = "WILL NOT MEET" in comm.upper() or "WILL NOT MEET" in desc.upper()
    if is_cancelled_db or is_will_not_meet:
        m['DisplayTime'] = "CANCELLED"
        
    extracted_link = extract_agenda_link(desc)
    m['LinkURL'] = extracted_link if extracted_link else m.get("LinkURL")
    m['ScrapedBills'] = []
    processed_events.append(m)

# --- HYBRID ENGINE: STEP 2 (REGEX INJECTION) ---
with st.spinner("Step 2: Scraping Official Dockets..."):
    scrape_tasks = []
    for e in processed_events:
        link = e.get("LinkURL")
        is_cancelled = "CANCEL" in str(e.get("DisplayTime", "")).upper()
        
        if link and not e['IsFloor'] and not e['IsCaucus'] and not is_cancelled:
            scrape_tasks.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPES) as executor:
        future_to_event = {executor.submit(scrape_docket_for_bills, e.get("LinkURL")): e for e in scrape_tasks}
        for future in concurrent.futures.as_completed(future_to_event):
            event = future_to_event[future]
            try:
                event['ScrapedBills'] = future.result(timeout=5)
            except Exception:
                pass

# --- BUILD UI DISPLAY MAP ---
display_map = {}
for e in processed_events:
    d = e['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(e)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found.")
else:
    sorted_dates = sorted(display_map.keys())[:7] 
    cols = st.columns(len(sorted_dates))
    
    for i, date_val in enumerate(sorted_dates):
        with cols[i]:
            st.markdown(f"### {date_val.strftime('%a')}")
            st.caption(date_val.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[date_val]
            day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            
            for event in day_events:
                name = str(event.get("OwnerName")).replace("Virginia ", "").replace(" of Delegates", "").strip()
                time_display = event.get("DisplayTime")
                agenda_link = event.get("LinkURL")
                is_floor = event.get("IsFloor")
                is_caucus = event.get("IsCaucus")
                is_cancelled = "CANCEL" in str(time_display).upper()
                scraped_bills = event.get("ScrapedBills", [])
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled / Will Not Meet")
                    st.divider()
                    continue
                
                if is_floor:
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        if "TBA" in str(time_display): st.warning("Time TBA")
                        else: st.success(f"⏰ {time_display}")
                        if agenda_link: st.link_button("View Floor Calendar", agenda_link)
                elif is_caucus:
                    with st.container():
                        st.markdown(f"**{name}**")
                        st.caption(f"👥 {time_display} (Caucus / Internal)")
                        st.divider()
                else:
                    with st.container():
                        if "TBA" in str(time_display):
                            st.caption("Time TBA")
                        elif len(str(time_display)) > 15:
                            st.markdown(f"**{time_display}**") 
                        else:
                            st.markdown(f"**⏰ {time_display}**")
                            
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        if "DOCUMENT_DETECTED" in scraped_bills:
                            st.info("📄 File Uploaded (PDF/Word)")
                        elif scraped_bills:
                            st.markdown("**Bills on Docket:**")
                            st.markdown("`" + "`, `".join(scraped_bills) + "`")
                        elif agenda_link and not scraped_bills:
                            st.caption("*No specific bills detected (or organizational).*")
                        else:
                            st.caption("*Agenda Pending*")

                        if agenda_link:
                            st.link_button("Official Agenda", agenda_link)
                        
                        st.divider()
