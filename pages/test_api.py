import streamlit as st
import requests
import re
from datetime import datetime, timedelta
import concurrent.futures

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261" 

st.set_page_config(page_title="v90 Agenda View", page_icon="📜", layout="wide")
st.title("📆 v90: The Master Calendar (With Agendas)")

# --- SPEED ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('https://', adapter)

# --- HELPER: TEXT CLEANING ---
def clean_html(text):
    if not text: return ""
    text = text.replace("<br>", " ").replace("</br>", " ")
    return re.sub('<[^<]+?>', '', text).strip()

# --- HELPER: BILL SCANNER (NEW) ---
def extract_bills_from_text(text):
    """
    Scans text for bill patterns like 'HB123', 'S.B. 45', 'H.R. 10'
    Returns a sorted list of unique bills.
    """
    if not text: return []
    
    # Regex looks for:
    # 1. Start of word boundary
    # 2. H, S (House/Senate)
    # 3. B, J, R (Bill, Joint Res, Res)
    # 4. Optional dots/spaces
    # 5. Digits
    pattern = r'\b([HS][BJR]\.?\s*\d+)\b'
    
    matches = re.findall(pattern, text, re.IGNORECASE)
    
    # Clean up formatting (e.g. "h.b. 100" -> "HB 100")
    clean_bills = []
    for m in matches:
        clean = m.upper().replace(".", "").replace(" ", "")
        # Insert space before number for readability (HB100 -> HB 100)
        formatted = re.sub(r'([A-Z]+)(\d+)', r'\1 \2', clean)
        clean_bills.append(formatted)
        
    return sorted(list(set(clean_bills)))

# --- HELPER: COMPLEX TIME EXTRACTOR ---
def extract_complex_time(text):
    if not text: return None
    clean = clean_html(text)
    lower = clean.lower()
    
    if "cancel" in lower or "postpone" in lower: return "CANCELLED"

    keywords = [
        "adjournment", "adjourn", "upon", "immediate", "rise of", 
        "recess", "after the", "completion of", "conclusion of",
        "commence", "convening", "15 minutes", "30 minutes",
        "1/2 hr", "half hour"
    ]
    
    if len(clean) < 150 and any(k in lower for k in keywords):
        return clean.strip()

    match = re.search(r'(\d{1,2}:\d{2}\s*[aA|pP]\.?[mM]\.?)', clean)
    if match: return match.group(1).upper()
    
    return None

def extract_agenda_link(description_html):
    if not description_html: return None
    match = re.search(r'href=[\'"]?([^\'" >]+)', description_html)
    if match:
        url = match.group(1)
        if url.startswith("/"): return f"https://house.vga.virginia.gov{url}"
        return url
    return None

# --- SORTING LOGIC ---
def parse_time_rank(time_str):
    if not time_str: return 9999
    t_upper = time_str.upper()
    if "CANCEL" in t_upper: return 8888
    if "TBA" in t_upper: return 9999
    if "ADJOURN" in t_upper or "UPON" in t_upper or "RISE" in t_upper: return 2000 
    try:
        match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M)', t_upper)
        if match:
            dt = datetime.strptime(match.group(1), "%I:%M %p")
            return dt.hour * 60 + dt.minute
    except: pass
    return 9999

# --- API FETCH ---
@st.cache_data(ttl=600) 
def get_full_schedule():
    url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            h = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "H"}, timeout=5)
            s = executor.submit(session.get, url, headers=headers, params={"sessionCode": SESSION_CODE, "chamberCode": "S"}, timeout=5)
            
            raw_items = []
            if h.result().status_code == 200: raw_items.extend(h.result().json().get("Schedules", []))
            if s.result().status_code == 200: raw_items.extend(s.result().json().get("Schedules", []))
            
        return raw_items
    except Exception as e:
        st.error(f"API Error: {e}")
        return []

# --- MAIN APP LOGIC ---

with st.spinner("Syncing Official Schedule..."):
    all_raw_items = get_full_schedule()

processed_events = []
seen_sigs = set()

for m in all_raw_items:
    raw_date = m.get("ScheduleDate", "").split("T")[0]
    if not raw_date: continue
    
    sig = (raw_date, m.get('ScheduleTime'), m.get('OwnerName'))
    if sig in seen_sigs: continue
    seen_sigs.add(sig)

    m['DateObj'] = datetime.strptime(raw_date, "%Y-%m-%d").date()
    
    # Text Processing
    desc_text = m.get("Description", "")
    comm_text = m.get("Comments", "")
    full_text = f"{desc_text} {comm_text}"
    
    m['AgendaLink'] = extract_agenda_link(desc_text)
    m['DetectedBills'] = extract_bills_from_text(full_text) # SCAN FOR BILLS
    
    name = m.get("OwnerName", "")
    is_floor = "Convene" in name or "Session" in name or name in ["House", "Senate"]
    
    api_time = m.get("ScheduleTime")
    final_time = api_time
    if not final_time: final_time = extract_complex_time(comm_text)
    if not final_time: final_time = extract_complex_time(desc_text)
    
    if not final_time:
        if is_floor: final_time = "Time TBA" 
        else: final_time = "CANCELLED"
            
    m['DisplayTime'] = final_time
    m['IsFloor'] = is_floor
    
    processed_events.append(m)

# Filter Future
today = datetime.now().date()
upcoming_events = [e for e in processed_events if e['DateObj'] >= today]

# Build Display Map
display_map = {}
for e in upcoming_events:
    d = e['DateObj']
    if d not in display_map: display_map[d] = []
    display_map[d].append(e)

# --- RENDER UI ---
if not display_map:
    st.info("No upcoming events found in API.")
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
                name = event.get("OwnerName").replace("Virginia ", "").replace(" of Delegates", "")
                time_display = event.get("DisplayTime")
                agenda_link = event.get("AgendaLink")
                is_floor = event.get("IsFloor")
                bills = event.get("DetectedBills", [])
                
                is_cancelled = "CANCEL" in str(time_display).upper()
                
                if is_cancelled:
                    st.error(f"❌ **{name}**")
                    st.caption("Time Not Listed / Cancelled")
                
                elif is_floor:
                    with st.container(border=True):
                        st.markdown(f"**🏛️ {name}**")
                        if "TBA" in str(time_display):
                            st.warning("Time TBA")
                            st.caption("*Pending Motion*")
                        else:
                            st.success(f"⏰ {time_display}")
                        if agenda_link: st.link_button("View Calendar", agenda_link)
                
                else:
                    # COMMITTEE CARD
                    with st.container():
                        if "TBA" in str(time_display): st.caption("Time TBA")
                        elif len(str(time_display)) > 15: st.markdown(f"**{time_display}**")
                        else: st.markdown(f"**⏰ {time_display}**")
                            
                        clean_name = name.replace("Committee", "").strip()
                        st.markdown(f"{clean_name}")
                        if "Subcommittee" in clean_name: st.caption("↳ Subcommittee")

                        # --- THE AGENDA DROPDOWN (v90 Feature) ---
                        # Logic: Show dropdown if bills exist OR if a link exists
                        has_content = len(bills) > 0 or agenda_link is not None
                        
                        if has_content:
                            label = f"📜 Agenda ({len(bills)})" if bills else "📜 Agenda"
                            with st.expander(label):
                                if bills:
                                    for b in bills:
                                        st.markdown(f"- **{b}**")
                                        
                                if agenda_link:
                                    st.markdown("---")
                                    st.link_button("🔗 View Official Doc", agenda_link)
                                elif not bills:
                                    st.caption("No specific bills listed in API feed.")
                        else:
                            # If no bills and no link, show nothing (cleaner)
                            st.caption("*(No Agenda Uploaded)*")
                        
                        st.divider()
