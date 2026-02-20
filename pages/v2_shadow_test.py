import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures
import time
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
SESSION_CODE = "20261"
MAX_CONCURRENT_SCRAPES = 3  # Protect against LIS Azure 503 Ban Hammer

st.set_page_config(page_title="v90 Hybrid API Calendar", page_icon="📆", layout="wide")
st.title("📆 v90: Global API Calendar (Hybrid Engine)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
session.mount('https://', adapter)

# --- HELPER: REGEX DOCKET SCRAPER ---
def scrape_docket_for_bills(link_url):
    """
    Safely fetches the HTML from the LinkURL and runs a strict regex 
    to extract Virginia bill numbers (e.g., HB100, SB20).
    """
    if not link_url:
        return []
    
    if str(link_url).lower().endswith(".pdf"):
        return ["PDF_AGENDA_DETECTED"]
        
    try:
        time.sleep(0.1) # Micro-stagger to avoid Azure WAF triggering
        resp = session.get(link_url, timeout=5)
        if resp.status_code != 200:
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        text_content = soup.get_text(" ", strip=True)
        
        # Strict Regex: Captures HB100, SB 20, HJ5, SR 12
        pattern = r'\b([HS][BJR]\s?\d+)\b'
        matches = re.findall(pattern, text_content, re.IGNORECASE)
        
        # Clean and deduplicate (e.g., convert "HB 100" to "HB100")
        clean_bills = []
        for m in matches:
            clean_b = m.upper().replace(" ", "")
            if clean_b not in clean_bills:
                clean_bills.append(clean_b)
                
        return clean_bills
        
    except Exception as e:
        return []

# --- API FETCH: STEP 1 ---
@st.cache_data(ttl=600)
def get_global_schedule_grid():
    """
    Step 1 of Hybrid Engine: Fetch the absolute truth of the schedule grid.
    """
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    today_str = datetime.now().strftime("%Y-%m-%d")
    next_week_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    # Passing startDate and endDate natively to the API
    params = {
        "sessionCode": SESSION_CODE,
        "startDate": today_str,
        "endDate": next_week_str
    }
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Fetch for both House and Senate concurrently
            h_params = params.copy(); h_params["chamberCode"] = "H"
            s_params = params.copy(); s_params["chamberCode"] = "S"
            
            h_future = executor.submit(session.get, url, headers=headers, params=h_params, timeout=5)
            s_future = executor.submit(session.get, url, headers=headers, params=s_params, timeout=5)
            
            raw_items = []
            if h_future.result().status_code == 200: raw_items.extend(h_future.result().json().get("ListItems", []))
            if s_future.result().status_code == 200: raw_items.extend(s_future.result().json().get("ListItems", []))
            
        return raw_items
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

# --- SORTING LOGIC ---
def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = time_str.upper()
    if "CANCEL" in t_upper: return 8888
    if "ADJOURN" in t_upper or "UPON" in t_upper or "RISE" in t_upper or "AFTER" in t_upper: return 2000 
    
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- MAIN ENGINE EXECUTION ---

with st.spinner("Step 1: Fetching API Master Grid..."):
    all_raw_items = get_global_schedule_grid()

processed_events = []
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = datetime.strptime(raw_date, "%Y-%m-%d").date()
    m['DisplayTime'] = m.get("ScheduleTime", "Time TBA")
    
    name = str(m.get("OwnerName", ""))
    is_floor = "Convene" in name or "Session" in name or name in ["House", "Senate"]
    m['IsFloor'] = is_floor
    
    # Official API Cancellation Truth
    if m.get("IsCancelled") is True:
        m['DisplayTime'] = "CANCELLED"
        
    m['ScrapedBills'] = []
    processed_events.append(m)

today = datetime.now().date()
upcoming_events = [e for e in processed_events if e['DateObj'] >= today]

# --- HYBRID ENGINE: STEP 2 (REGEX INJECTION) ---
with st.spinner("Step 2: Scraping Official Dockets via Regex..."):
    scrape_tasks = []
    for e in upcoming_events:
        link = e.get("LinkURL")
        is_cancelled = e.get("IsCancelled") is True
        
        # Bypass scraping if it's a Floor Session, Cancelled, or has no Link
        if link and not e['IsFloor'] and not is_cancelled:
            scrape_tasks.append(e)

    # Multi-threading the Regex Scraper (Capped at 3 to prevent WAF bans)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPES) as executor:
        future_to_event = {executor.submit(scrape_docket_for_bills, e.get("LinkURL")): e for e in scrape_tasks}
        for future in concurrent.futures.as_completed(future_to_event):
            event = future_to_event[future]
            try:
                event['ScrapedBills'] = future.result()
            except Exception:
                event['ScrapedBills'] = []

# --- BUILD UI DISPLAY MAP ---
display_map = {}
for e in upcoming_events:
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
                is_cancelled = event.get("IsCancelled") is True
                scraped_bills = event.get("ScrapedBills", [])
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled by Clerk")
                    st.divider()
                    continue
                
                if is_floor:
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        if "TBA" in str(time_display):
                            st.warning("Time TBA")
                        else:
                            st.success(f"⏰ {time_display}")
                        if agenda_link: st.link_button("View Floor Calendar", agenda_link)
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

                        if "PDF_AGENDA_DETECTED" in scraped_bills:
                            st.info("📄 PDF Agenda Uploaded")
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
