import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta
import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup 

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
BILLS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
SUBS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Subscribers"

# --- VIRGINIA LIS DATA FEEDS ---
LIS_BASE_URL = "https://lis.blob.core.windows.net/lisfiles/20261/"
LIS_BILLS_CSV = LIS_BASE_URL + "BILLS.CSV"       
LIS_HISTORY_CSV = LIS_BASE_URL + "HISTORY.CSV"
DEFAULT_SESSION_ID = "261" 

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- TOPIC CATEGORIES ---
TOPIC_KEYWORDS = {
    "🗳️ Elections & Democracy": ["election", "vote", "ballot", "campaign", "poll", "voter", "registrar", "districting", "suffrage"],
    "🏗️ Housing & Property": ["rent", "landlord", "tenant", "housing", "lease", "property", "zoning", "eviction", "homeowner", "development", "residential"],
    "✊ Labor & Workers Rights": ["wage", "salary", "worker", "employment", "labor", "union", "bargaining", "leave", "compensation", "workplace", "employee", "minimum", "overtime"],
    "💰 Economy & Business": ["tax", "commerce", "business", "market", "consumer", "corporation", "finance", "budget", "economic", "trade"],
    "🎓 Education": ["school", "education", "student", "university", "college", "teacher", "curriculum", "scholarship", "tuition", "board of education"],
    "🚓 Public Safety & Law": ["firearm", "gun", "police", "crime", "penalty", "court", "judge", "enforcement", "prison", "arrest", "criminal", "justice"],
    "🏥 Health & Healthcare": ["health", "medical", "hospital", "patient", "doctor", "insurance", "care", "mental", "pharmacy", "drug", "medicaid"],
    "🌳 Environment & Energy": ["energy", "water", "pollution", "environment", "climate", "solar", "conservation", "waste", "carbon", "natural resources", "wind", "power", "electricity", "hydroelectric", "nuclear", "chesapeake", "bay", "river", "watershed"],
    "🚗 Transportation": ["road", "highway", "vehicle", "driver", "license", "transit", "traffic", "transportation", "motor"],
    "💻 Tech & Utilities": ["internet", "broadband", "data", "privacy", "utility", "cyber", "technology", "telecom", "artificial intelligence"],
    "⚖️ Civil Rights": ["discrimination", "rights", "equity", "minority", "gender", "religious", "freedom", "speech"],
}

# --- HELPER FUNCTIONS ---

def get_smart_subject(title):
    title_lower = str(title).lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords): return category
    return "📂 Unassigned / General"

def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    clean = re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)
    return clean

def determine_lifecycle(status_text, committee_name):
    status = str(status_text).lower()
    comm = str(committee_name).strip()
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]): return "✅ Signed & Enacted"
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]): return "❌ Dead / Tabled"
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]): return "✍️ Awaiting Signature"
    out_keywords = ["reported", "passed", "agreed", "engrossed", "communicated", "reading waived", "read second", "read third"]
    if any(x in status for x in out_keywords): return "📣 Out of Committee"
    if comm not in ["-", "nan", "None", ""] and len(comm) > 3: return "📥 In Committee"
    return "📥 In Committee"

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return ""
    name = str(name).strip()
    
    # 1. REMOVE NAMES (Strict Regex)
    name = re.sub(r'\b[A-Z][a-z]+, [A-Z]\. ?[A-Z]?\.?.*$', '', name) 
    name = re.sub(r'\b(Simon|Rasoul|Willett|Helmer|Lucas|Surovell|Locke|Deeds|Favola|Marsden|Ebbin|McPike|Hayes|Carroll Foy|Subcommittee #\d+)\b.*', '', name, flags=re.IGNORECASE)
    
    # 2. MAP TO STANDARD
    upper = name.upper().strip()
    mapping = {
        "HED": "House Education", "HAPP": "House Appropriations", "FIN": "Senate Finance",
        "JUD": "Courts of Justice", "GL": "General Laws", "AG": "Agriculture", "TRAN": "Transportation",
        "P&E": "Privileges & Elections", "C&L": "Commerce & Labor", "HWI": "House Health, Welfare & Inst.",
        "COUNTIES CITIES AND TOWNS": "House Counties, Cities & Towns",
        "COMMUNICATIONS TECHNOLOGY AND INNOVATION": "House Communications & Tech"
    }
    for k, v in mapping.items():
        if k in upper: return v
        
    return name.strip().title()

def clean_status_text(text):
    if not text: return ""
    text = str(text)
    return text.replace("HED", "House Education").replace("sub:", "Subcommittee:")

# --- SMART HTML CALENDAR SCRAPER ---
@st.cache_data(ttl=600)
def fetch_html_calendar():
    """
    Scrapes Schedule + BILL NUMBERS if visible in the text.
    """
    calendar_data = {}
    debug_log = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. HOUSE SCRAPER
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
            
            current_date_str = None
            for i, line in enumerate(lines):
                # Detect Date
                if "JANUARY" in line.upper() or "FEBRUARY" in line.upper():
                    try:
                        clean_d = line.split("–")[0].split("-")[0].strip()
                        if "2026" not in clean_d: clean_d += ", 2026"
                        dt = datetime.strptime(clean_d, "%A, %B %d, %Y")
                        current_date_str = dt.strftime("%Y-%m-%d")
                    except: pass
                
                # Detect Time
                if current_date_str:
                    time_match = re.search(r'^\d{1,2}:\d{2}\s*[AP]M', line)
                    if time_match:
                        mtg_time = time_match.group(0)
                        if i > 0:
                            raw_name = lines[i-1]
                            if "Agenda" not in raw_name and "Meeting" not in raw_name:
                                full_name = f"House {raw_name}"
                                
                                # NEW: Scan 5 lines ahead/behind for Bill Numbers (e.g. HB 123)
                                context_text = " ".join(lines[max(0, i-2):min(len(lines), i+15)]).upper()
                                found_bills = re.findall(r'\b(HB|SB|HJ|SJ)\s?(\d+)\b', context_text)
                                clean_found = [f"{b[0]}{b[1]}" for b in found_bills]
                                
                                if current_date_str not in calendar_data: calendar_data[current_date_str] = []
                                calendar_data[current_date_str].append({
                                    "Time": mtg_time,
                                    "Committee": clean_committee_name(full_name),
                                    "Chamber": "House",
                                    "BillsFound": clean_found
                                })
            debug_log.append(f"House Scraper: Success")
    except Exception as e:
        debug_log.append(f"House Scraper Error: {e}")

    # 2. SENATE SCRAPER
    try:
        url = "https://apps.senate.virginia.gov/Senator/ComMeetings.php"
        resp = requests.get(url, headers=headers, timeout=4)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
            
            for i, line in enumerate(lines):
                if "2026" in line and ("AM" in line or "PM" in line):
                    try:
                        parts = line.split("2026")
                        if len(parts) > 1:
                            date_part = parts[0] + "2026"
                            time_part = parts[1].strip()
                            dt = datetime.strptime(date_part.strip(), "%A, %B %d, %Y")
                            d_str = dt.strftime("%Y-%m-%d")
                            if i > 0:
                                raw_name = lines[i-1]
                                if "Cancelled" not in raw_name:
                                    full_name = f"Senate {raw_name}"
                                    
                                    # NEW: Scan nearby text for bill IDs
                                    context_text = " ".join(lines[max(0, i-2):min(len(lines), i+15)]).upper()
                                    found_bills = re.findall(r'\b(HB|SB|HJ|SJ)\s?(\d+)\b', context_text)
                                    clean_found = [f"{b[0]}{b[1]}" for b in found_bills]

                                    if d_str not in calendar_data: calendar_data[d_str] = []
                                    calendar_data[d_str].append({
                                        "Time": time_part,
                                        "Committee": clean_committee_name(full_name),
                                        "Chamber": "Senate",
                                        "BillsFound": clean_found
                                    })
                    except: pass
            debug_log.append(f"Senate Scraper: Success")
    except Exception as e:
        debug_log.append(f"Senate Scraper Error: {e}")

    return calendar_data, debug_log

# --- DATA FETCHING ---
@st.cache_data(ttl=300) 
def fetch_lis_data():
    data = {}
    est = pytz.timezone('US/Eastern')
    data['fetch_time'] = datetime.now(est).strftime("%I:%M %p EST")
    def load_csv(url):
        try:
            df = pd.read_csv(url, encoding='ISO-8859-1', on_bad_lines='skip', low_memory=False)
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
            return df
        except: return pd.DataFrame()
    data['bills'] = load_csv(LIS_BILLS_CSV)
    if not data['bills'].empty:
        col = 'bill_number' if 'bill_number' in data['bills'].columns else 'bill_id'
        if col in data['bills'].columns: data['bills']['bill_clean'] = data['bills'][col].astype(str).apply(clean_bill_id)
    
    data['history'] = load_csv(LIS_HISTORY_CSV)
    if not data['history'].empty:
        col = 'bill_number' if 'bill_number' in data['history'].columns else 'bill_id'
        if col in data['history'].columns: data['history']['bill_clean'] = data['history'][col].astype(str).apply(clean_bill_id)
    return data

def get_bill_data_batch(bill_numbers, lis_data_dict):
    lis_df = lis_data_dict.get('bills', pd.DataFrame())
    history_df = lis_data_dict.get('history', pd.DataFrame())
    results = []
    clean_bills = list(set([clean_bill_id(b) for b in bill_numbers if str(b).strip() != 'nan']))
    lis_lookup = {}
    if not lis_df.empty and 'bill_clean' in lis_df.columns:
        lis_lookup = lis_df.set_index('bill_clean').to_dict('index')
    history_lookup = {}
    if not history_df.empty and 'bill_clean' in history_df.columns:
        for b_id, group in history_df.groupby('bill_clean'):
            history_lookup[b_id] = group.to_dict('records')

    for bill_num in clean_bills:
        item = lis_lookup.get(bill_num)
        title = "Unknown"; status = "Not Found"; date_val = ""; curr_comm = "-"; curr_sub = "-"; history_data = []
        if item:
            title = item.get('bill_description', 'No Title')
            status = item.get('last_house_action', '')
            if pd.isna(status) or str(status).strip() == '': status = item.get('last_senate_action', 'Introduced')
            date_val = str(item.get('last_house_action_date', ''))
            if not date_val or date_val == 'nan': date_val = str(item.get('last_senate_action_date', ''))
        raw_history = history_lookup.get(bill_num, [])
        if raw_history:
            for h_row in raw_history:
                desc = ""; date_h = ""
                for col in ['history_description', 'description', 'action', 'history']:
                    if col in h_row and pd.notna(h_row[col]): desc = str(h_row[col]); break
                for col in ['history_date', 'date', 'action_date']:
                    if col in h_row and pd.notna(h_row[col]): date_h = str(h_row[col]); break
                if desc:
                    history_data.append({"Date": date_h, "Action": desc})
                    desc_lower = desc.lower()
                    if "referred to" in desc_lower:
                        match = re.search(r'referred to (?:committee on|the committee on)?\s?([a-z\s&,]+)', desc_lower)
                        if match:
                            found = match.group(1).strip().title()
                            if len(found) > 3: curr_comm = found
                    if "sub:" in desc_lower:
                        try:
                            parts = desc_lower.split("sub:")
                            curr_sub = parts[1].strip().title()
                        except: pass
        if curr_comm == "-":
            potential_cols = ['last_house_committee', 'last_senate_committee', 'house_committee', 'senate_committee']
            if item:
                for col in potential_cols:
                    val = item.get(col)
                    if pd.notna(val) and str(val).strip() not in ['nan', '', '-', '0']: curr_comm = str(val).strip(); break
        curr_comm = clean_committee_name(curr_comm)
        if curr_comm and "Senate" not in curr_comm and "House" not in curr_comm:
             if bill_num.startswith("SB") or bill_num.startswith("SJ") or bill_num.startswith("SR"): curr_comm = f"Senate {curr_comm}"
             elif bill_num.startswith("HB") or bill_num.startswith("HJ") or bill_num.startswith("HR"): curr_comm = f"House {curr_comm}"
        lifecycle = determine_lifecycle(str(status), str(curr_comm))
        display_comm = curr_comm
        if lifecycle == "📣 Out of Committee" or lifecycle == "✅ Signed & Enacted":
             if "engross" in str(status).lower(): display_comm = "🏛️ Engrossed (Passed Chamber)"
             elif "read" in str(status).lower(): display_comm = "📜 On Floor (Read/Reported)"
             elif "passed" in str(status).lower(): display_comm = "🎉 Passed Chamber"
             else: display_comm = "On Floor / Reported"
        results.append({
            "Bill Number": bill_num, "Official Title": title, "Status": str(status), "Date": date_val, 
            "Lifecycle": lifecycle, "Auto_Folder": get_smart_subject(title), "History_Data": history_data[::-1], 
            "Current_Committee": str(curr_comm).strip(), "Display_Committee": str(display_comm).strip(), "Current_Sub": str(curr_sub).strip()
        })
    return pd.DataFrame(results) if results else pd.DataFrame()

# --- UI COMPONENTS ---
def render_bill_card(row):
    if row.get('Official Title') not in ["Unknown", "Error", "Not Found", None]: display_title = row['Official Title']
    else: display_title = row.get('My Title', 'No Title Provided')
    st.markdown(f"**{row['Bill Number']}**")
    my_status = str(row.get('My Status', '')).strip()
    if my_status and my_status != 'nan' and my_status != '-': st.info(f"🏷️ **Status:** {my_status}")
    st.caption(f"{display_title}"); st.caption(f"_{clean_status_text(row.get('Status'))}_"); st.divider()

def render_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    def rename_unassigned(name):
        name = str(name).strip()
        if name in ['-', 'nan', 'None', '', '0']: return "Unassigned"
        if name == "House -": return "House - Unassigned"
        if name == "Senate -": return "Senate - Unassigned"
        if name.endswith("-"): return name + " Unassigned"
        return name
    df['Display_Comm_Group'] = df['Current_Committee'].fillna('-').apply(rename_unassigned)
    df['Current_Sub'] = df['Current_Sub'].fillna('-')
    def sort_key(name): return ("Unassigned" in name, name)
    unique_committees = sorted(df['Display_Comm_Group'].unique(), key=sort_key)
    for comm_name in unique_committees:
        if "Unassigned" in comm_name: st.markdown(f"##### 📂 {comm_name}")
        else: st.markdown(f"##### 🏛️ {comm_name}")
        comm_df = df[df['Display_Comm_Group'] == comm_name]
        unique_subs = sorted([s for s in comm_df['Current_Sub'].unique() if s != '-'])
        if '-' in comm_df['Current_Sub'].unique(): unique_subs.insert(0, '-')
        for sub_name in unique_subs:
            if sub_name != '-': st.markdown(f"**↳ {sub_name}**") 
            sub_df = comm_df[comm_df['Current_Sub'] == sub_name]
            for i, row in sub_df.iterrows(): _render_single_bill_row(row)

def render_simple_list_item(df):
    if df.empty: st.caption("No bills."); return
    for i, row in df.iterrows(): _render_single_bill_row(row)

def _render_single_bill_row(row):
    header_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', '')
    my_status = str(row.get('My Status', '')).strip()
    label_text = f"{row['Bill Number']}"
    if my_status and my_status != 'nan' and my_status != '-': label_text += f" - {my_status}"
    if header_title: label_text += f" - {header_title}"
    with st.expander(label_text):
        st.markdown(f"**🏛️ Current Status:** {row.get('Display_Committee', '-')}")
        if row.get('Current_Sub') and row.get('Current_Sub') != '-': st.markdown(f"**↳ Subcommittee:** {row.get('Current_Sub')}")
        st.markdown(f"**📌 Designated Title:** {row.get('My Title', '-')}")
        st.markdown(f"**📜 Official Title:** {row.get('Official Title', '-')}")
        st.markdown(f"**🔄 Status:** {clean_status_text(row.get('Status', '-'))}")
        hist_data = row.get('History_Data', [])
        if isinstance(hist_data, list) and hist_data:
            st.markdown("**📜 History:**"); st.dataframe(pd.DataFrame(hist_data), hide_index=True, use_container_width=True)
        else: st.caption(f"Date: {row.get('Date', '-')}")
        lis_link = f"https://lis.virginia.gov/bill-details/20261/{row['Bill Number']}"
        st.markdown(f"🔗 [View Official Bill on LIS]({lis_link})")

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")
est = pytz.timezone('US/Eastern')
current_time_est = datetime.now(est).strftime("%I:%M %p EST")
if 'last_run' not in st.session_state: st.session_state['last_run'] = current_time_est

# --- SIDEBAR ---
demo_mode = st.sidebar.checkbox("🛠️ Enable Demo Mode", value=False)
col_btn, col_time = st.columns([1, 6])
with col_btn:
    if st.button("🔄 Check for Updates"):
        st.session_state['last_run'] = datetime.now(est).strftime("%I:%M %p EST")
        st.cache_data.clear(); st.rerun()
with col_time: st.markdown(f"**Last Refreshed:** `{st.session_state['last_run']}`")

# 1. LOAD USER DATA
try:
    raw_df = pd.read_csv(BILLS_URL)
    raw_df.columns = raw_df.columns.str.strip()
    try: subs_df = pd.read_csv(SUBS_URL)
    except: subs_df = pd.DataFrame(columns=["Email"])
    cols_w = ['Bills Watching', 'Title (Watching)']
    if 'Status (Watching)' in raw_df.columns: cols_w.append('Status (Watching)')
    df_w = pd.DataFrame()
    if 'Bills Watching' in raw_df.columns:
        df_w = raw_df[cols_w].copy()
        new_cols = ['Bill Number', 'My Title']
        if 'Status (Watching)' in raw_df.columns: new_cols.append('My Status')
        df_w.columns = new_cols
        df_w['Type'] = 'Watching'
    df_i = pd.DataFrame()
    w_col_name = next((c for c in raw_df.columns if "Working On" in c and "Title" not in c and "Status" not in c), None)
    if w_col_name:
        cols_i = [w_col_name]
        title_work_col = next((c for c in raw_df.columns if "Title (Working)" in c), None)
        if title_work_col: cols_i.append(title_work_col)
        status_work_col = next((c for c in raw_df.columns if "Status (Working)" in c), None)
        if status_work_col: cols_i.append(status_work_col)
        df_i = raw_df[cols_i].copy()
        i_new_cols = ['Bill Number']
        if title_work_col: i_new_cols.append('My Title')
        if status_work_col: i_new_cols.append('My Status')
        df_i.columns = i_new_cols
        if 'My Title' not in df_i.columns: df_i['My Title'] = "-"
        df_i['Type'] = 'Involved'
    sheet_df = pd.concat([df_w, df_i], ignore_index=True).dropna(subset=['Bill Number'])
    sheet_df['Bill Number'] = sheet_df['Bill Number'].apply(clean_bill_id)
    sheet_df = sheet_df[sheet_df['Bill Number'] != 'NAN']
    sheet_df = sheet_df.drop_duplicates(subset=['Bill Number'])
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")
    if 'My Status' not in sheet_df.columns: sheet_df['My Status'] = "-"
except Exception as e: st.error(f"Sheet Error: {e}"); st.stop()

# 2. FETCH DATA
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()
html_calendar, scrape_logs = fetch_html_calendar() # Run smart scraper

if bills_to_track:
    if demo_mode:
        import random
        mock_results = []
        for b in bills_to_track:
            mock_results.append({
                "Bill Number": b, "Official Title": "[DEMO] Bill Title", "Status": "Referred to Commerce",
                "Lifecycle": "🚀 Active", "Auto_Folder": "💰 Economy & Business",
                "My Title": "Demo Title", "Date": "2026-01-14",
                "History_Data": [], "Current_Committee": "Commerce", "Current_Sub": "-", "My Status": "Demo Status"
            })
        api_df = pd.DataFrame(mock_results)
    else:
        api_df = get_bill_data_batch(bills_to_track, lis_data)

    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    if 'Auto_Folder' not in final_df.columns or final_df['Auto_Folder'].isnull().any():
         final_df['Auto_Folder'] = final_df.apply(lambda row: get_smart_subject(row.get('Official Title', row.get('My Title', ''))), axis=1)

    # 3. RENDER TABS
    tab_involved, tab_watching, tab_upcoming = st.tabs(["🚀 Directly Involved", "👀 Watching", "📅 Upcoming Hearings"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            st.subheader("🗂️ Browse by Topic")
            unique_folders = sorted(subset['Auto_Folder'].unique())
            cols = st.columns(3)
            for i, folder in enumerate(unique_folders):
                with cols[i % 3]:
                    bills_in_folder = subset[subset['Auto_Folder'] == folder]
                    with st.expander(f"{folder} ({len(bills_in_folder)})"):
                        for _, row in bills_in_folder.iterrows(): render_bill_card(row)
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            
            in_comm = subset[subset['Lifecycle'] == "📥 In Committee"]
            out_comm = subset[subset['Lifecycle'] == "📣 Out of Committee"]
            passed = subset[subset['Lifecycle'].isin(["✅ Signed & Enacted", "✍️ Awaiting Signature"])]
            failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown("#### 📥 In Committee"); render_grouped_list_item(in_comm)
            with m2: st.markdown("#### 📣 Out of Committee"); render_simple_list_item(out_comm)
            with m3: st.markdown("#### 🎉 Passed"); render_simple_list_item(passed)
            with m4: st.markdown("#### ❌ Failed"); render_simple_list_item(failed)

    # --- TAB 3: CALENDAR (SMART SCRAPER) ---
    with tab_upcoming:
        st.subheader("📅 Your Confirmed Agenda")
        today = datetime.now(est).date()
        current_dt = datetime.now(est)
        cols = st.columns(7)
        
        bill_info_map = final_df.set_index('Bill Number')[['Current_Committee', 'Current_Sub', 'My Status', 'Status', 'Date', 'Lifecycle']].to_dict('index')

        for i in range(7):
            target_date = today + timedelta(days=i)
            target_date_str = target_date.strftime('%Y-%m-%d')
            display_date_str = target_date.strftime("%a %m/%d")
            with cols[i]:
                st.markdown(f"**{display_date_str}**")
                st.divider()
                events_found = False
                bills_shown_today = set()
                
                if target_date_str in html_calendar:
                    meetings = html_calendar[target_date_str]
                    for m in meetings:
                        # Time Check (Skip past meetings)
                        try:
                            t_str = m['Time'].split("(")[0].strip()
                            mtg_dt_str = f"{target_date_str} {t_str}"
                            mtg_dt = datetime.strptime(mtg_dt_str, "%Y-%m-%d %I:%M %p")
                            mtg_dt = est.localize(mtg_dt)
                            if mtg_dt < current_dt: continue 
                        except: pass

                        # Logic:
                        # 1. Did scraper see specific bill numbers? (m['BillsFound'])
                        # 2. If not, does the committee name match any of our bills? (Inference)
                        
                        confirmed_bills = []
                        potential_bills = []
                        
                        # Check confirmed bills first
                        if 'BillsFound' in m and m['BillsFound']:
                            for b_num in m['BillsFound']:
                                if b_num in bill_info_map:
                                    confirmed_bills.append(b_num)
                        
                        # Fallback to committee matching if no confirmed bills found
                        if not confirmed_bills:
                            comm_clean = m['Committee'].lower().replace("committee", "").strip()
                            for b_id, info in bill_info_map.items():
                                if info.get('Lifecycle') in ["✅ Signed & Enacted", "❌ Dead / Tabled"]: continue
                                b_comm = str(info.get('Current_Committee', '')).lower()
                                if comm_clean in b_comm or b_comm in comm_clean:
                                    potential_bills.append(b_id)

                        # RENDER
                        if confirmed_bills:
                            events_found = True
                            st.markdown(f"**{m['Committee']}**")
                            st.caption(f"⏰ {m['Time']}")
                            st.success("✅ Confirmed on Docket")
                            for b_id in confirmed_bills:
                                bills_shown_today.add(b_id)
                                info = bill_info_map.get(b_id, {})
                                st.error(f"**{b_id}**")
                            st.divider()
                        elif potential_bills:
                            events_found = True
                            st.markdown(f"**{m['Committee']}**")
                            st.caption(f"⏰ {m['Time']}")
                            st.warning("⚠️ Potential Hearing")
                            
                            # Official Link
                            mmdd = datetime.strptime(target_date_str, "%Y-%m-%d").strftime("%m%d")
                            link = f"https://lis.virginia.gov/cgi-bin/legp604.exe?{DEFAULT_SESSION_ID}+doc+DO{mmdd}"
                            st.markdown(f"[📄 View Official Docket]({link})")
                            st.divider()

                # PLAN C: TODAY COMPLETED
                if i == 0: 
                    history_groups = {}
                    for b_id, info in bill_info_map.items():
                        if b_id in bills_shown_today: continue
                        last_date = str(info.get('Date', '')); is_today = False
                        if last_date == target_date_str: is_today = True
                        else:
                            try: lis_dt = datetime.strptime(last_date, "%m/%d/%Y").date(); is_today = (lis_dt == target_date)
                            except: pass
                        if is_today:
                            lis_status = str(info.get('Status', ''))
                            skip_keywords = ["referred", "printed", "presentation", "reading waived"]
                            is_outcome = any(x in lis_status.lower() for x in ["reported", "passed", "defeat", "stricken", "agreed", "read", "engross", "vote", "assigned"])
                            is_admin = any(x in lis_status.lower() for x in skip_keywords)
                            if is_admin and not is_outcome: continue
                            events_found = True
                            raw_comm = str(info.get('Current_Committee', '')); 
                            if raw_comm in ["-", "nan", "None", ""]: raw_comm = ""
                            if "fiscal" in lis_status.lower(): group_name = "Fiscal Impact Report"
                            elif b_id.startswith(("HJ", "SJ", "HR", "SR")): group_name = "Floor Session"
                            elif not raw_comm:
                                if any(x in lis_status.lower() for x in ["read", "pass", "engross", "defeat"]): group_name = "Floor Session / Action"
                                else: group_name = "General Assembly Action"
                            else: group_name = clean_committee_name(raw_comm)
                            if group_name not in history_groups: history_groups[group_name] = []
                            history_groups[group_name].append(b_id)
                    for g_name, b_list in history_groups.items():
                        st.markdown(f"**{g_name}**"); st.caption("⏰ Completed / Actioned")
                        for b_id in b_list:
                            info = bill_info_map.get(b_id, {}); status_text = ""; raw_status = str(info.get('My Status', '')).strip()
                            if raw_status and raw_status != 'nan' and raw_status != '-': status_text = f" - {raw_status}"
                            st.error(f"**{b_id}**{status_text}"); st.caption(f"_{clean_status_text(info.get('Status'))}_"); st.divider()
                if not events_found: st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("System Status:")
        hist_cols = st.session_state.get('history_cols', [])
        if 'history' in lis_data and not lis_data['history'].empty: st.write(f"**History File:** 🟢 Loaded ({len(lis_data['history'])} rows)")
        else: st.write(f"**History File:** 🔴 Not loaded")
        
        st.write(f"**HTML Scraper:** {'🟢 Active' if html_calendar else '🔴 Empty'}")
        st.write("**Scraper Log:**")
        st.text("\n".join(scrape_logs[:10]))
