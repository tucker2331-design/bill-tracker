import streamlit as st
import requests
import re
import time
import random
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v95 Glass Box", page_icon="🔍", layout="wide")
st.title("🔍 v95: The 'Glass Box' (Fixes + Dev Tool)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Connection': 'keep-alive'
}

# --- HELPER FUNCTIONS ---
def clean_html(text):
    if not text: return ""
    text = text.replace("&nbsp;", " ").replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

def normalize_name(name):
    if not name: return ""
    # Remove generic words to focus on unique identifiers (Commerce, Labor, Courts, Justice)
    clean = name.lower().replace("-", " ")
    for word in ["house", "senate", "committee", "subcommittee", "room", "building", "capitol", "of", "and", "&", "the"]:
        clean = clean.replace(word, "")
    return " ".join(clean.split())

def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    if "TBA" in t_upper: return 9999
    if "ADJOURN" in t_upper or "UPON" in t_upper: return 2000 
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- 1. VISUAL SCRAPER (Row-Based) ---
def fetch_visual_schedule_data(date_obj):
    """
    Scrapes the LIS Daily Schedule (dys) by ROW to keep links attached to text.
    Returns: List of dicts {text, link, tokens}
    """
    time.sleep(random.uniform(0.1, 0.3))
    date_str = date_obj.strftime("%Y%m%d")
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{SESSION_CODE}+dys+{date_str}"
    
    results = []
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # LIS schedule usually uses <ul> or <table>. We scan all block elements.
        # We grab the text and ANY link found inside that block.
        for elem in soup.find_all(['li', 'tr', 'p', 'div']):
            text = clean_html(elem.get_text(" ", strip=True))
            if len(text) < 5: continue # Skip empty noise
            
            # Find Best Link in this row
            link = None
            for a in elem.find_all('a', href=True):
                href = a['href']
                if href.startswith("/"): href = f"https://lis.virginia.gov{href}"
                
                # We specifically want Docket or Committee Info
                a_text = a.get_text().lower()
                if "docket" in a_text or "info" in a_text:
                    link = href
                    break # Found the gold, stop looking in this row
            
            results.append({
                "text": text,
                "clean_tokens": set(normalize_name(text).split()),
                "extracted_link": link
            })
            
        return results
    except Exception as e:
        return [{"error": str(e)}]

# --- 2. BILL SCRAPER ---
def scan_agenda_page(url):
    time.sleep(random.uniform(0.1, 0.3))
    if not url: return []
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(" ", strip=True)
        
        # Regex for bills (matches HB100, S.B. 50, etc.)
        bills = re.findall(r'\b(H\.?B\.?|S\.?B\.?|H\.?J\.?|S\.?J\.?)\s*(\d+)', text, re.IGNORECASE)
        clean = set()
        for p, n in bills:
            clean.add(f"{p.upper().replace('.','').strip()}{n}")
        
        def n_sort(s):
            parts = re.match(r"([A-Za-z]+)(\d+)", s)
            if parts: return parts.group(1), int(parts.group(2))
            return s, 0
        return sorted(list(clean), key=n_sort)
    except: return []

# --- 3. API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: raw_items.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw_items.extend(s.result().json().get("Schedules", []))
            return raw_items
    except: return []

# --- MAIN LOGIC ---

with st.spinner("Initializing..."):
    all_raw_items = get_full_schedule()

today = datetime.now().date()
tasks_bills = []
needed_days = set()
processed_events = []
seen_sigs = set()

# Pre-Process
for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue 
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = d
    m['AgendaLink'] = None # Default
    
    # Check API Description for a link
    desc_html = m.get("Description", "")
    if desc_html:
        soup = BeautifulSoup(desc_html, 'html.parser')
        a_tag = soup.find('a', href=True)
        if a_tag: 
            href = a_tag['href']
            if href.startswith("/"): href = f"https://house.vga.virginia.gov{href}"
            m['AgendaLink'] = href
    
    if not m.get("OwnerName"): m["OwnerName"] = "Unknown Committee"
    
    needed_days.add(d)
    if m['AgendaLink']: tasks_bills.append(m['AgendaLink'])
    processed_events.append(m)

# Parallel Fetch
schedule_cache = {}
bill_cache = {}

if needed_days or tasks_bills:
    with st.spinner(f"Snatching Links & Checking Bills..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            f_sched = {executor.submit(fetch_visual_schedule_data, d): d for d in needed_days}
            f_bills = {executor.submit(scan_agenda_page, url): url for url in tasks_bills}
            
            for f in concurrent.futures.as_completed(f_sched):
                try: schedule_cache[f_sched[f]] = f.result()
                except: pass
            
            for f in concurrent.futures.as_completed(f_bills):
                try: bill_cache[f_bills[f]] = f.result()
                except: pass

# --- MERGE & MATCH LOGIC ---
display_map = {}
# For the Developer Tool
debug_log = {} 

for m in processed_events:
    name = m.get("OwnerName", "Unknown")
    api_time = m.get("ScheduleTime")
    d = m['DateObj']
    
    final_time = api_time
    source_label = "API"
    
    # Store debug info for this committee
    m_debug = {
        "api_name": name,
        "api_tokens": normalize_name(name).split(),
        "visual_rows_scanned": 0,
        "best_match_score": 0,
        "matched_row_text": None,
        "link_action": "None"
    }
    
    # VISUAL OVERRIDE
    if d in schedule_cache:
        rows = schedule_cache[d]
        my_tokens = set(normalize_name(name).split())
        m_debug["visual_rows_scanned"] = len(rows)
        
        for i, row in enumerate(rows):
            row_tokens = row['clean_tokens']
            
            # SCORE MATCHING (Fix for Cancelled)
            # We calculate intersection score instead of strict subset
            if not my_tokens: break
            
            intersection = my_tokens.intersection(row_tokens)
            score = len(intersection) / len(my_tokens)
            
            if score > m_debug["best_match_score"]:
                m_debug["best_match_score"] = score
                m_debug["matched_row_text"] = row['text']
            
            # Threshold: 60% match required
            if score > 0.6:
                # 1. LINK SNATCH (Fix for Senate Commerce)
                if not m['AgendaLink'] and row['extracted_link']:
                    m['AgendaLink'] = row['extracted_link']
                    m_debug["link_action"] = f"Snatched: {row['extracted_link']}"
                    source_label = "Link Snatched"
                    # Add to bill cache on the fly (won't populate this run, but link works)
                    
                # 2. CANCELLED CHECK (Fix for House Finance)
                # Check current row AND previous row
                prev_text = rows[i-1]['text'].lower() if i > 0 else ""
                row_text = row['text'].lower()
                
                if "cancel" in row_text or "cancel" in prev_text:
                    final_time = "CANCELLED"
                    source_label = "Sched (Cancelled)"
                    m_debug["status_action"] = "Marked Cancelled"
                    break
                
                # 3. TIME CHECK
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', row['text'])
                if time_match:
                    final_time = time_match.group(1).upper()
                    if source_label == "API": source_label = "Sched (Time)"
                    break
                
                if "adjourn" in row_text or "upon" in row_text:
                    final_time = "Upon Adjournment"
                    if source_label == "API": source_label = "Sched (Time)"
                    break

    if not final_time or final_time == "TBA":
        if "Convene" in name: final_time = "Time TBA"
        else: final_time = "Time Not Listed"

    m['DisplayTime'] = final_time
    m['Bills'] = bill_cache.get(m['AgendaLink'], [])
    m['Source'] = source_label
    
    # Add to debug log
    debug_log[f"{name} ({d.strftime('%m/%d')})"] = m_debug
    
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

# --- RENDER ---
# SIDEBAR DEV TOOL
st.sidebar.header("🛠️ Developer X-Ray")
st.sidebar.write("Inspect what the code sees for a specific committee.")
selected_debug = st.sidebar.selectbox("Select Committee:", options=list(debug_log.keys()))

if selected_debug:
    data = debug_log[selected_debug]
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Committee:** `{data['api_name']}`")
    st.sidebar.markdown(f"**Match Score:** `{data['best_match_score']:.2f}` (Needs > 0.6)")
    st.sidebar.markdown(f"**Matched Line:**")
    st.sidebar.caption(f"{data['matched_row_text']}")
    st.sidebar.markdown(f"**Link Action:** `{data['link_action']}`")
    st.sidebar.markdown("---")


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
                raw_name = event.get("OwnerName") or "Unknown"
                name = raw_name.replace("Virginia ", "").replace(" of Delegates", "")
                
                time_display = event.get("DisplayTime")
                agenda_link = event.get("AgendaLink")
                bills = event.get("Bills", [])
                
                is_cancelled = "CANCEL" in str(time_display).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        # TIME
                        if "TBA" in str(time_display) or "Not Listed" in str(time_display):
                            st.caption(f"⚠️ {time_display}")
                        elif len(str(time_display)) > 15:
                            st.markdown(f"**{time_display}**")
                        else:
                            st.markdown(f"**⏰ {time_display}**")
                        
                        # NAME
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        # BILLS
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("View List"):
                                st.write(", ".join(bills))
                                if agenda_link: st.link_button("View Docket/Agenda", agenda_link)
                        elif agenda_link:
                            st.link_button("View Docket/Agenda", agenda_link)
                        else:
                            st.caption("*(No Link)*")
