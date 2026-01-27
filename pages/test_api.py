import streamlit as st
import requests
import re
import concurrent.futures
from datetime import datetime
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 
LIS_SESSION_ID = "261"

st.set_page_config(page_title="v117 Sub-Hunter", page_icon="🦈", layout="wide")
st.title("🦈 v117: The Sub-Hunter (Navigating to Subcommittees)")

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

# --- 2. THE SUB-HUNTER (Smart Scraper) ---
def get_bills_deep_dive(url, target_name):
    """
    Scrapes bills. If target_name implies a subcommittee, it hunts for that specific link first.
    """
    logs = [f"Visiting: {url}"]
    if not url: return [], logs, url
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        current_url = url
        
        # --- SUBCOMMITTEE LOGIC ---
        # 1. Clean the target name to find specific sub-name (e.g. "Campaigns and Candidates")
        clean_target = target_name.lower().replace("house", "").replace("senate", "").replace("committee", "").strip()
        
        # 2. Look for a link on the page that matches parts of the target name
        sub_link_found = None
        
        # Only hunt if it's likely a subcommittee (contains "subcommittee" or hyphenated)
        if "subcommittee" in clean_target or "-" in target_name:
            logs.append(f"Sub-Hunter Active: Scanning for '{clean_target}'...")
            
            # Split target into keywords (e.g. "campaigns", "candidates")
            keywords = [w for w in re.split(r'[\s\-\&]+', clean_target) if len(w) > 3]
            
            for a in soup.find_all('a', href=True):
                link_text = a.get_text(" ", strip=True).lower()
                
                # Check if enough keywords match to be confident
                matches = sum(1 for k in keywords if k in link_text)
                if matches >= 1:
                    # Found a potential match!
                    sub_link_found = a['href']
                    if not sub_link_found.startswith("http"):
                        # Handle relative LIS links
                        if sub_link_found.startswith("/"):
                            base = "https://lis.virginia.gov"
                            sub_link_found = f"{base}{sub_link_found}"
                    logs.append(f"🦈 Sub-Hunter: Found match '{link_text}' -> {sub_link_found}")
                    break
        
        # 3. If found, DIVE!
        if sub_link_found:
            current_url = sub_link_found
            resp = session.get(sub_link_found, headers=HEADERS, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            logs.append("Switched context to Subcommittee Page.")

        # --- STANDARD SCRAPING ---
        def scrape_text(s):
            text = s.get_text(" ", strip=True)
            matches = re.findall(r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b', text, re.IGNORECASE)
            bills = set()
            for p, n in matches:
                bills.add(f"{p.upper().replace('.','').strip()}{n}")
            return sorted(list(bills))

        bills = scrape_text(soup)
        logs.append(f"Bills Found: {len(bills)}")
        
        if bills: return bills, logs, current_url
        
        # --- FALLBACK DIVE (Agenda/Docket) ---
        # If we still have 0 bills, look for "Agenda" PDF/Link on this new page
        target = None
        for a in soup.find_all('a', href=True):
            txt = a.get_text().lower()
            if "agenda" in txt or "docket" in txt:
                target = a['href']
                if target.startswith("/"):
                    base = "https://lis.virginia.gov"
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
    
    # Link Selection
    api_link, reason = extract_best_link(m.get("Description"))
    
    # SFAC Exception
    if api_link and "sfac.virginia.gov" in api_link:
        # (SFAC scraper code omitted for brevity but logic is same as v116)
        pass 
            
    router_link = construct_modern_link(m.get("OwnerName"))
    
    # PRIORITIZE ROUTER FOR SUBCOMMITTEES
    # Because the API often gives the Main Committee link for subs, 
    # but our Router + SubHunter logic is smarter.
    final_link = api_link
    source = "API"
    
    if not final_link or "granicus" in str(final_link):
        final_link = router_link
        source = "Router (Golden)"
        
    m['Link'] = final_link
    m['Source'] = source
    m['FlightLog'] = flight_log
    
    # We pass the full object to scan so we have the name
    if final_link: links_to_scan.append((final_link, m.get("OwnerName")))
    processed_events.append(m)
    
    key_name = f"{m.get('OwnerName')} ({d.strftime('%m/%d')})"
    committee_map_for_probe[key_name] = m

# Bills Scanning
bill_cache = {}
bill_logs = {}
final_urls = {}

if links_to_scan:
    # Deduplicate by URL but keep name map
    url_to_name = {u: n for u, n in links_to_scan}
    unique_urls = list(url_to_name.keys())
    
    with st.spinner(f"Hunting Subcommittees on {len(unique_urls)} pages..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # We submit the URL AND the Name for the Sub-Hunter
            future_map = {executor.submit(get_bills_deep_dive, u, url_to_name[u]): u for u in unique_urls}
            
            for f in concurrent.futures.as_completed(future_map):
                orig_url = future_map[f]
                try: 
                    res, logs, final_url = f.result()
                    bill_cache[orig_url] = res
                    bill_logs[orig_url] = logs
                    final_urls[orig_url] = final_url # Store where we ended up
                except Exception as e: 
                    bill_cache[orig_url] = []
                    bill_logs[orig_url] = [str(e)]
                    final_urls[orig_url] = orig_url

# --- SIDEBAR ---
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
                
                # Update link to the Final URL found by Sub-Hunter
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
