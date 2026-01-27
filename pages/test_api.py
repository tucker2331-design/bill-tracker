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

st.set_page_config(page_title="v116 Golden Master", page_icon="🏛️", layout="wide")
st.title("🏛️ v116: The Golden Master (Corrected ID Map)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# --- 1. THE GOLDEN MAP (Derived from your v115 Scan) ---
# Maps keywords to the CONFIRMED 2026 IDs.
HOUSE_MAP = {
    "agriculture": "H01",
    "chesapeake": "H01",
    "appropriations": "H02",
    "counties": "H07",
    "cities": "H07",
    "courts": "H08",
    "education": "H09",
    "finance": "H10",
    "general laws": "H11",
    "labor": "H14",
    "commerce": "H14", # Labor and Commerce
    "energy": "H14",
    "public safety": "H15",
    "privileges": "H18",
    "elections": "H18",
    "transportation": "H19",
    "rules": "H20",
    "communications": "H21",
    "technology": "H21",
    "health": "H24",
    "human services": "H24",
}

SENATE_MAP = {
    "agriculture": "S01",
    "commerce": "S02",
    "labor": "S02",
    "education": "S04",
    "health": "S04",
    "finance": "S05",
    "appropriations": "S05",
    "local": "S07",
    "privileges": "S08",
    "elections": "S08",
    "rehabilitation": "S09",
    "social": "S09",
    "rules": "S10",
    "transportation": "S11",
    "general laws": "S12",
    "courts": "S13",
    "justice": "S13",
}

def construct_modern_link(owner_name):
    """
    Routes ALL committees to the Modern LIS 2026 portal using the Golden Map.
    """
    if not owner_name: return None
    name_lower = owner_name.lower()
    cid = None
    
    # 1. Determine Chamber
    is_senate = "senate" in name_lower
    is_house = "house" in name_lower or not is_senate # Default to House if unclear, but usually clear
    
    target_map = SENATE_MAP if is_senate else HOUSE_MAP
    
    # 2. Find ID
    for keyword, id_val in target_map.items():
        if keyword in name_lower:
            cid = id_val
            break # Stop at first match (Map is ordered by specificity implicitly)
    
    if not cid: return None
    
    # 3. Universal Pattern
    return f"https://lis.virginia.gov/session-details/{SESSION_CODE}/committee-information/{cid}/committee-details"

# --- 2. SFAC SAFE SCRAPER ---
def scrape_sfac_site(url, target_date_obj, target_name):
    logs = [f"SFAC Scrape: {url}"]
    try:
        resp = session.get(url, headers=HEADERS, timeout=3)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        target_str = target_date_obj.strftime("%B %-d, %Y")
        if "%-" in target_str: target_str = target_date_obj.strftime("%B %d, %Y").replace(" 0", " ")
        logs.append(f"Searching date: {target_str}")

        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 4: continue
            
            meeting_name = cols[0].get_text(" ", strip=True).lower()
            meeting_date = cols[1].get_text(" ", strip=True)
            
            if target_str not in meeting_date: continue
            
            api_sub = "subcommittee" in target_name.lower()
            row_sub = "subcommittee" in meeting_name
            if api_sub != row_sub: continue
            
            raw_time = cols[2].get_text(" ", strip=True)
            time_clean = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', raw_time)
            final_time = time_clean.group(1).upper() if time_clean else raw_time
            
            agenda_link = None
            for a in cols[3].find_all('a', href=True):
                if "agenda" in a.get_text().lower():
                    agenda_link = a['href']
                    if not agenda_link.startswith("http"):
                        agenda_link = f"https://sfac.virginia.gov{agenda_link}"
                    break
            
            logs.append(f"Match Found: {final_time}")
            return {"Time": final_time, "Link": agenda_link}, logs
    except Exception as e:
        logs.append(f"Error: {e}")
        return None, logs
    return None, logs

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
        
        # 🗑️ TRASH
        if "granicus" in u or "now_playing" in u or "broadcast" in u or "video" in u: 
            continue 
        
        # 🥇 GOLD
        if "agenda" in u or "docket" in u or ".pdf" in u: score = 10
        # 🥈 SILVER
        elif "/committees/" in u or "session-details" in u: score = 5
        # 🥉 BRONZE
        else: score = 1
        
        if score > best_score:
            best_score = score
            best_link = url
            reason = f"Score {score}"
            
    return best_link, reason

# --- 4. BILL SCRAPER ---
def get_bills_deep_dive(url):
    logs = [f"Visiting: {url}"]
    if not url: return [], logs
    
    try:
        resp = session.get(url, headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        def scrape_text(s):
            text = s.get_text(" ", strip=True)
            matches = re.findall(r'\b([H|S]\.?[B|J|R]\.?)\s*(\d+)\b', text, re.IGNORECASE)
            bills = set()
            for p, n in matches:
                bills.add(f"{p.upper().replace('.','').strip()}{n}")
            return sorted(list(bills))

        bills = scrape_text(soup)
        logs.append(f"Surface: {len(bills)} bills")
        if bills: return bills, logs
        
        # Dive
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
            logs.append(f"Diving: {target}")
            resp2 = session.get(target, headers=HEADERS, timeout=5)
            bills = scrape_text(BeautifulSoup(resp2.text, 'html.parser'))
            logs.append(f"Deep: {len(bills)} bills")
            return bills, logs
            
        return [], logs
    except Exception as e:
        logs.append(f"Error: {e}")
        return [], logs

# --- 5. API FETCH ---
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

with st.spinner("Syncing..."):
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
    
    # Link
    api_link, reason = extract_best_link(m.get("Description"))
    flight_log.append(f"API Logic: {reason} -> {api_link}")
    
    if api_link and "sfac.virginia.gov" in api_link:
        sfac, slogs = scrape_sfac_site(api_link, d, m.get("OwnerName", ""))
        flight_log.extend(slogs)
        if sfac:
            if sfac['Time']: m['DisplayTime'] = sfac['Time']
            if sfac['Link']: api_link = sfac['Link']
            if "CANCEL" in str(sfac['Time']).upper(): m['DisplayTime'] = "CANCELLED"
            
    router_link = construct_modern_link(m.get("OwnerName"))
    flight_log.append(f"Golden Router: {router_link}")
    
    final_link = api_link if api_link else router_link
    m['Link'] = final_link
    m['Source'] = "API-Extract" if api_link else "Router (Golden)"
    m['FlightLog'] = flight_log
    
    if final_link: links_to_scan.append(final_link)
    processed_events.append(m)
    
    key_name = f"{m.get('OwnerName')} ({d.strftime('%m/%d')})"
    committee_map_for_probe[key_name] = m

# Bills
bill_cache = {}
bill_logs = {}
if links_to_scan:
    unique = list(set(links_to_scan))
    with st.spinner(f"Scanning {len(unique)} Dockets..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            fut = {executor.submit(get_bills_deep_dive, u): u for u in unique}
            for f in concurrent.futures.as_completed(fut):
                url = fut[f]
                try: 
                    res, logs = f.result()
                    bill_cache[url] = res
                    bill_logs[url] = logs
                except Exception as e: 
                    bill_cache[url] = []
                    bill_logs[url] = [str(e)]

# --- SIDEBAR: FLIGHT RECORDER & PROBE ---
st.sidebar.header("🕹️ Control Panel")

# Probe
with st.sidebar.expander("🔴 Live Probe"):
    selected_c = st.selectbox("Select Committee:", options=list(committee_map_for_probe.keys()))
    if selected_c:
        evt = committee_map_for_probe[selected_c]
        target_url = evt['Link']
        st.write(f"**Target:** {target_url}")
        
        if st.button("Ping URL"):
            try:
                r = requests.get(target_url, headers=HEADERS, timeout=5)
                st.write(f"**Status:** `{r.status_code}`")
                if "agenda" in r.text.lower() or "docket" in r.text.lower():
                    st.success("✅ Content Found.")
                else:
                    st.warning("⚠️ No 'Agenda' text.")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()
        st.write("**Logs:**")
        for l in evt['FlightLog']: st.write(f"- {l}")
        if target_url in bill_logs:
            for l in bill_logs[target_url]: st.write(f"- {l}")

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
                                if link: st.link_button("View Docket", link)
                        elif link:
                            st.link_button("View Docket", link)
                        else:
                            st.caption("*(No Link)*")
                        
                        st.caption(f"Src: {src}")
