import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
LIS_SESSION_ID = "261"

st.set_page_config(page_title="v119 Section Scanner", page_icon="🧬", layout="wide")
st.title("🧬 v119: The Section Scanner (Targeted Sub-Hunting)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 1. THE GOLDEN MAP (Confirmed IDs) ---
HOUSE_MAP = {
    "agriculture": "H01", "chesapeake": "H01", "appropriations": "H02",
    "counties": "H07", "cities": "H07", "courts": "H08", "education": "H09",
    "finance": "H10", "general laws": "H11", "labor": "H14", "commerce": "H14",
    "energy": "H14", "public safety": "H15", "privileges": "H18", "elections": "H18",
    "transportation": "H19", "rules": "H20", "communications": "H21", "technology": "H21",
    "health": "H24", "human services": "H24",
}

SENATE_MAP = {
    "agriculture": "S01", "commerce": "S02", "labor": "S02", "education": "S04",
    "health": "S04", "finance": "S05", "appropriations": "S05", "local": "S07",
    "privileges": "S08", "elections": "S08", "rehabilitation": "S09", "social": "S09",
    "rules": "S10", "transportation": "S11", "general laws": "S12", "courts": "S13",
    "justice": "S13",
}

def construct_modern_link(owner_name):
    if not owner_name: return None
    name_lower = owner_name.lower()
    cid = None
    is_senate = "senate" in name_lower
    target_map = SENATE_MAP if is_senate else HOUSE_MAP
    
    for keyword, id_val in target_map.items():
        if keyword in name_lower:
            cid = id_val
            break
            
    if not cid: return None
    return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{cid}/committee-details"

# --- 2. THE SECTION SCANNER (Targeted Sub-Hunter) ---
def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def get_bills_deep_dive(url, target_name):
    logs = [f"Visiting: {url}"]
    if not url: return [], logs, url
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        current_url = url
        
        # --- PHASE 1: SUBCOMMITTEE SECTION SCAN ---
        clean_target = target_name.lower().replace("house", "").replace("senate", "").replace("committee", "").strip()
        is_sub_target = "subcommittee" in clean_target or "-" in target_name
        
        # Only hunt if we suspect this is a subcommittee event
        if is_sub_target and "committee-details" in url:
            logs.append(f"Sub-Hunter: Active for '{clean_target}'")
            
            # Find "Subcommittees" Header
            sub_header = soup.find(string=re.compile("Subcommittees", re.IGNORECASE))
            
            candidate_links = []
            
            if sub_header:
                # Look in the container/list immediately following the header
                # We search the parent's siblings or children
                container = sub_header.find_parent()
                if container:
                    # Expand search to nearby elements (parent's parent) to catch the list
                    search_area = container.find_parent() 
                    if search_area:
                        for a in search_area.find_all('a', href=True):
                            link_text = a.get_text(" ", strip=True)
                            candidate_links.append((link_text, a['href']))
            
            # If no header found, just scan ALL links on page as fallback
            if not candidate_links:
                logs.append("⚠️ 'Subcommittees' header not found. Scanning all links.")
                for a in soup.find_all('a', href=True):
                    candidate_links.append((a.get_text(" ", strip=True), a['href']))
            
            # LOG CANDIDATES (For Debugging)
            logs.append(f"Candidates found: {[c[0] for c in candidate_links[:5]]}...")

            # FUZZY MATCHING
            best_match = None
            best_score = 0
            
            # Split target into key words (e.g. "Campaigns", "Candidates")
            target_words = [w for w in re.split(r'[\s\-\&]+', clean_target) if len(w) > 3]
            
            for txt, href in candidate_links:
                txt_lower = txt.lower()
                
                # Score 1: Keyword overlap
                matches = sum(1 for w in target_words if w in txt_lower)
                
                # Score 2: Sequence Similarity (0.0 - 1.0)
                sim = similarity(clean_target, txt_lower)
                
                # Decision
                if matches >= 1 and sim > best_score:
                    best_score = sim
                    best_match = href
            
            if best_match and best_score > 0.3: # Threshold
                logs.append(f"🦈 Match Found (Score {best_match}): {best_match}")
                
                # Fix Relative URL
                if not best_match.startswith("http"):
                    if best_match.startswith("/"): best_match = f"https://lis.virginia.gov{best_match}"
                
                # DIVE!
                current_url = best_match
                resp = session.get(best_match, headers=HEADERS, timeout=5)
                soup = BeautifulSoup(resp.text, 'html.parser')
                logs.append("Switched context to Subcommittee Page.")
            else:
                logs.append("❌ No matching subcommittee link found.")

        # --- PHASE 2: BILL SCRAPING ---
        def scrape_text(s):
            text = s.get_text(" ", strip=True)
            matches = re.findall(r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b', text, re.IGNORECASE)
            bills = set()
            for p, n in matches:
                bills.add(f"{p.upper().replace('.','').strip()}{n}")
            return sorted(list(bills))

        bills = scrape_text(soup)
        logs.append(f"Bills on page: {len(bills)}")
        
        if bills: return bills, logs, current_url
        
        # --- PHASE 3: DOCKET FALLBACK ---
        # If 0 bills, look for 'Agenda' link on this specific page
        target = None
        for a in soup.find_all('a', href=True):
            txt = a.get_text().lower()
            if "agenda" in txt or "docket" in txt:
                target = a['href']
                if target.startswith("/"):
                    base = "https://house.vga.virginia.gov" if "house.vga" in url else "https://lis.virginia.gov"
                    target = f"{base}{target}"
                break
        
        if target:
            logs.append(f"Diving to Docket: {target}")
            current_url = target
            resp2 = session.get(target, headers=HEADERS, timeout=5)
            bills = scrape_text(BeautifulSoup(resp2.text, 'html.parser'))
            logs.append(f"Deep Bills: {len(bills)}")
            return bills, logs, current_url
            
        return [], logs, current_url
        
    except Exception as e:
        logs.append(f"Error: {e}")
        return [], logs, url

# --- 3. LINK EXTRACTOR ---
def extract_best_link(desc_text):
    if not desc_text: return None, "No Desc"
    all_links = re.findall(r'href=[\'"]?(https?://[^\'" >]+)', desc_text)
    if not all_links: return None, "No Hrefs"
    
    best_link = None
    best_score = -1
    reason = "None"
    
    for url in all_links:
        score = 0
        u = url.lower()
        if "granicus" in u or "now_playing" in u or "broadcast" in u or "video" in u: continue 
        
        if "agenda" in u or "docket" in u or ".pdf" in u: score = 10
        elif "/committees/" in u or "session-details" in u: score = 5
        else: score = 1
        
        if score > best_score:
            best_score = score
            best_link = url
            reason = f"Score {score}"
            
    return best_link, reason

# --- 4. API FETCH ---
@st.cache_data(ttl=600)
def fetch_api_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    events = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            for f in [h, s]:
                if f.result().status_code == 200:
                    events.extend(f.result().json().get("Schedules", []))
    except: pass
    return events

def parse_time_rank(time_str):
    if not time_str or "TBA" in str(time_str): return 9999
    t_upper = str(time_str).upper()
    if "CANCEL" in t_upper: return 8888
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- MAIN LOGIC ---

with st.spinner("Processing Schedule..."):
    raw_events = fetch_api_schedule()

today = datetime.now().date()
processed_events = []
links_to_scan = []
committee_map_for_probe = {}

for m in raw_events:
    if not m: continue
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    d = datetime.strptime(raw_date, "%Y-%m-%d").date()
    if d < today: continue
    
    m['DateObj'] = d
    flight_log = []
    
    # Time
    api_time = m.get("ScheduleTime")
    m['DisplayTime'] = api_time if api_time else "Time TBA"
    if m.get("IsCancelled") is True: m['DisplayTime'] = "CANCELLED"
    
    # Link Priority: API -> Router
    api_link, reason = extract_best_link(m.get("Description"))
    router_link = construct_modern_link(m.get("OwnerName"))
    
    if api_link:
        final_link = api_link
        source = "API-Extract"
    else:
        final_link = router_link
        source = "Router (Golden)"
        
    m['Link'] = final_link
    m['Source'] = source
    m['FlightLog'] = flight_log
    
    if final_link: links_to_scan.append((final_link, m.get("OwnerName")))
    processed_events.append(m)
    
    key_name = f"{m.get('OwnerName')} ({d.strftime('%m/%d')})"
    committee_map_for_probe[key_name] = m

# Bills Scanning
bill_cache = {}
bill_logs = {}
final_urls = {}

if links_to_scan:
    url_to_name = {u: n for u, n in links_to_scan}
    unique_urls = list(url_to_name.keys())
    
    with st.spinner(f"Scanning {len(unique_urls)} Events..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_map = {executor.submit(get_bills_deep_dive, u, url_to_name[u]): u for u in unique_urls}
            for f in concurrent.futures.as_completed(future_map):
                orig_url = future_map[f]
                try: 
                    res, logs, final_url = f.result()
                    bill_cache[orig_url] = res
                    bill_logs[orig_url] = logs
                    final_urls[orig_url] = final_url
                except Exception as e: 
                    bill_cache[orig_url] = []
                    bill_logs[orig_url] = [str(e)]
                    final_urls[orig_url] = orig_url

# --- SIDEBAR PROBE ---
st.sidebar.header("🕹️ Control Panel")
with st.sidebar.expander("🔴 Live Probe"):
    selected_c = st.selectbox("Select Committee:", options=list(committee_map_for_probe.keys()))
    if selected_c:
        evt = committee_map_for_probe[selected_c]
        orig_url = evt['Link']
        st.write(f"**Start:** {orig_url}")
        if orig_url in final_urls:
            st.write(f"**End:** {final_urls[orig_url]}")
            
        st.write("**Logs:**")
        for l in evt['FlightLog']: st.write(f"- {l}")
        if orig_url in bill_logs:
            for l in bill_logs[orig_url]: st.write(f"- {l}")

# --- DISPLAY ---
display_map = {}
for m in processed_events:
    d = m['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(m)

if not display_map:
    st.info("No upcoming events.")
else:
    dates = sorted(display_map.keys())[:7]
    cols = st.columns(len(dates))
    
    for i, dv in enumerate(dates):
        with cols[i]:
            st.markdown(f"### {dv.strftime('%a')}")
            st.caption(dv.strftime('%b %d'))
            st.divider()
            
            day_events = display_map[dv]
            try: day_events.sort(key=lambda x: parse_time_rank(x.get("DisplayTime")))
            except: pass
            
            for e in day_events:
                if not e: continue
                name = e.get("OwnerName", "Unknown").replace("Committee", "").replace("Virginia", "").strip()
                time_s = e.get("DisplayTime")
                link = e.get("Link")
                src = e.get("Source")
                
                final_dest_link = final_urls.get(link, link)
                bills = bill_cache.get(link, [])
                
                is_cancelled = "CANCEL" in str(time_s).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Cancelled")
                else:
                    with st.container(border=True):
                        if "TBA" in str(time_s): st.warning(f"⚠️ {time_s}")
                        else: st.markdown(f"**⏰ {time_s}**")
                        
                        st.markdown(f"**{name}**")
                        
                        if bills:
                            st.success(f"**{len(bills)} Bills Listed**")
                            with st.expander("List"):
                                st.write(", ".join(bills))
                                if final_dest_link: st.link_button("View Docket", final_dest_link)
                        elif final_dest_link:
                            st.link_button("View Docket", final_dest_link)
                        else:
                            st.caption("*(No Link)*")
                        
                        st.caption(f"Src: {src}")
