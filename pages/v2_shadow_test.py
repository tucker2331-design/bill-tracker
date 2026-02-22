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
MAX_CONCURRENT_SCRAPES = 3  # Azure WAF Protection

st.set_page_config(page_title="v91 Absolute Calendar", page_icon="📆", layout="wide")
st.title("📆 v91: Global API Calendar (The Vault Engine)")

# --- STREAMLIT INFRASTRUCTURE ---
est = pytz.timezone('US/Eastern')
if st.sidebar.button("🔄 Clear Cache & Refresh Live"):
    st.cache_data.clear()
    st.sidebar.success("Cache cleared! Pulling fresh LIS data.")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: BULLETPROOF LINK EXTRACTOR ---
def get_best_link(description_html, chamber_code):
    """Bypasses WebEx traps and legacy Javascript onclick anchors."""
    if not description_html: return None
    
    # 1. Extract standard hrefs and legacy Javascript window.open links
    links = re.findall(r'href=[\'"]?([^\'" >]+)', description_html)
    js_links = re.findall(r'window\.open\([\'"]([^\'"]+)[\'"]\)', description_html)
    loc_links = re.findall(r'location\.href=[\'"]([^\'"]+)[\'"]', description_html)
    all_links = links + js_links + loc_links
    
    best_link = None
    for l in all_links:
        l_lower = l.lower()
        if any(bad in l_lower for bad in ["webex", "zoom", "streaming"]): continue
        best_link = l
        if any(good in l_lower for good in ["agenda", "docket", "view"]): break # Lock target
    
    # 2. Chamber-Specific Domain Routing
    if best_link and best_link.startswith("/"):
        if chamber_code == "H": return f"https://house.vga.virginia.gov{best_link}"
        else: return f"https://apps.senate.virginia.gov{best_link}"
        
    return best_link

# --- HELPER: BLOCK-VOTING & REGEX EXTRACTOR ---
def extract_bills_from_text(text_content):
    """Handles block-voting, substitute suffixes (S1), and strips zero-padding."""
    clean_bills = []
    
    # Matches prefix (HB) followed by numbers, optionally separated by commas/ands
    pattern = r'\b([HS][BJR])\s*((?:\d+(?:[A-Z]\d+)?)(?:\s*(?:,|&|and)\s*\d+(?:[A-Z]\d+)?)*)\b'
    matches = re.finditer(pattern, text_content, re.IGNORECASE)
    
    for match in matches:
        prefix = match.group(1).upper()
        numbers_string = match.group(2)
        
        # Split block votes (e.g., "10, 11 & 12" -> ["10", "11", "12"])
        individual_numbers = re.split(r',|&|and', numbers_string)
        
        for num_str in individual_numbers:
            num_clean = num_str.strip().upper().replace(" ", "")
            if not num_clean: continue
                
            raw_bill = f"{prefix}{num_clean}"
            # Zero-Padding Sanitization (HB0042S1 -> HB42S1)
            sanitized_bill = re.sub(r'^([A-Z]+)0+(\d+.*)$', r'\1\2', raw_bill)
            
            if sanitized_bill not in clean_bills:
                clean_bills.append(sanitized_bill)
                
    return clean_bills

def scrape_docket_for_bills(link_url):
    """Safely fetches HTML, aborts on binary files, and extracts pure bills."""
    if not link_url: return []
    
    # Legacy Tech File Intercept
    if any(ext in str(link_url).lower() for ext in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]):
        return ["DOCUMENT_DETECTED"]
        
    try:
        time.sleep(0.1) # WAF Ban Protection
        resp = session.get(link_url, timeout=5)
        if resp.status_code != 200: return []
            
        # HTML Adjacency Strip
        soup = BeautifulSoup(resp.text, 'html.parser')
        text_content = soup.get_text(" ", strip=True)
        
        return extract_bills_from_text(text_content)
    except Exception:
        return []

# --- API FETCH: ANTI-PAGINATION ENGINE ---
@st.cache_data(ttl=600)
def get_global_schedule_grid():
    """Fetches day-by-day to completely bypass the 100-item Azure pagination limit."""
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    
    today = datetime.now(est).date()
    raw_items = []
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(8): # Today + Next 7 Days
                target_date = (today + timedelta(days=i)).strftime("%Y-%m-%d")
                
                h_params = {"sessionCode": SESSION_CODE, "chamberCode": "H", "startDate": target_date, "endDate": target_date}
                s_params = {"sessionCode": SESSION_CODE, "chamberCode": "S", "startDate": target_date, "endDate": target_date}
                
                futures.append(executor.submit(session.get, url, headers=headers, params=h_params, timeout=5))
                futures.append(executor.submit(session.get, url, headers=headers, params=s_params, timeout=5))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    resp = future.result(timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_items.extend(data.get("Schedules", data.get("ListItems", [])))
                except Exception:
                    pass # Prevent endless thread hang
                    
        return raw_items
    except Exception as e:
        st.error(f"API Connection Error: {e}")
        return []

# --- SORTING LOGIC ---
def parse_time_rank(time_str):
    if not time_str: return 9999
    # Period Parser Crash Fix
    t_upper = time_str.upper().replace(".", "")
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

with st.spinner("Step 1: Fetching API Master Grid (Bypassing Pagination)..."):
    all_raw_items = get_global_schedule_grid()

processed_events = []
seen_ids = set() # Deduplication by official ScheduleId

for m in all_raw_items:
    # 1. Deduplication via ScheduleID to prevent Double-Meeting Drop
    sched_id = m.get('ScheduleId')
    if sched_id:
        if sched_id in seen_ids: continue
        seen_ids.add(sched_id)

    # 2. Timezone-Locked Date
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    date_obj = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if date_obj < datetime.now(est).date(): continue # Drop yesterday (UTC drift fix)
    m['DateObj'] = date_obj

    # 3. Relational Time / Whitespace Check
    sched_time = str(m.get("ScheduleTime", "")).strip()
    if sched_time:
        m['DisplayTime'] = sched_time
    else:
        # Waterfall check for relational time
        comm = str(m.get("Comments", "")).strip()
        desc = str(m.get("Description", "")).strip()
        if comm and any(x in comm.lower() for x in ["adjourn", "upon", "rise", "after"]): m['DisplayTime'] = comm
        elif desc and any(x in desc.lower() for x in ["adjourn", "upon", "rise", "after"]): m['DisplayTime'] = desc
        else: m['DisplayTime'] = "Time TBA"
    
    # 4. Identity & Bypasses
    name = str(m.get("OwnerName", "")).strip()
    clean_name = name.replace("Virginia ", "").replace(" of Delegates", "").strip()
    
    # Strict Regex for Floor Sessions (Exact Match Trap Fix)
    m['IsFloor'] = bool(re.match(r'^(House|Senate)(?:\s+Convenes|\s+Session)?$', clean_name, re.IGNORECASE))
    
    # Caucus Garbage Fetch Prevention
    m['IsCaucus'] = any(x in clean_name.upper() for x in ["CAUCUS", "DELEGATION", "PRAYER"])
    
    # 5. Dual-Layer Cancellation Check
    comm_desc_text = str(m.get("Comments", "")).upper() + " " + str(m.get("Description", "")).upper()
    is_cancelled_text = "CANCEL" in comm_desc_text or "WILL NOT MEET" in comm_desc_text
    if m.get("IsCancelled") is True or is_cancelled_text:
        m['DisplayTime'] = "CANCELLED"
    
    # 6. Target Lock
    chamber = "H" if "House" in clean_name else "S"
    extracted_link = get_best_link(m.get("Description", ""), chamber)
    m['LinkURL'] = extracted_link if extracted_link else m.get("LinkURL")
        
    m['ScrapedBills'] = []
    processed_events.append(m)

# --- HYBRID ENGINE: STEP 2 (REGEX INJECTION) ---
with st.spinner("Step 2: Scraping Official Dockets via Regex..."):
    scrape_tasks = []
    for e in processed_events:
        link = e.get("LinkURL")
        is_cancelled = "CANCEL" in str(e.get("DisplayTime", "")).upper()
        
        # Only scrape valid committees
        if link and not e['IsFloor'] and not e['IsCaucus'] and not is_cancelled:
            scrape_tasks.append(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPES) as executor:
        future_to_event = {executor.submit(scrape_docket_for_bills, e.get("LinkURL")): e for e in scrape_tasks}
        for future in concurrent.futures.as_completed(future_to_event):
            event = future_to_event[future]
            try:
                event['ScrapedBills'] = future.result(timeout=5)
            except Exception:
                event['ScrapedBills'] = []

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
                            st.markdown(f"**{time_display}**") # Adjournment relation
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
