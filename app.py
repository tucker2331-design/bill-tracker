import streamlit as st
import pandas as pd
import requests
import time
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
LIS_SUBDOCKET_CSV = LIS_BASE_URL + "SUBDOCKET.CSV"
LIS_DOCKET_CSV = LIS_BASE_URL + "DOCKET.CSV"
LIS_CALENDAR_CSV = LIS_BASE_URL + "CALENDAR.CSV"
LIS_HISTORY_CSV = LIS_BASE_URL + "HISTORY.CSV"

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- RESTORED: TOPIC CATEGORIES ---
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

def determine_lifecycle(status_text, committee_name):
    status = str(status_text).lower()
    comm = str(committee_name).strip()
    
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]):
        return "✅ Signed & Enacted"
    
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]):
        return "❌ Dead / Tabled"
    
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]):
        return "✍️ Awaiting Signature"
        
    exit_keywords = ["reported", "read", "passed", "agreed", "engrossed", "communicated"]
    
    has_committee = comm not in ["-", "nan", "None", ""]
    is_exiting = any(x in status for x in exit_keywords)
    
    if has_committee and not is_exiting:
        return "📥 In Committee"

    if any(x in status for x in ["referred", "assigned", "continued", "committee"]):
        return "📥 In Committee"
        
    return "📣 Out of Committee"

def get_smart_subject(title):
    title_lower = str(title).lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "📂 Unassigned / General"

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return ""
    name = str(name).strip()
    if "," in name: name = name.split(",")[0].strip()

    mapping = {
        "HED": "House Education", "HEDC": "House Education", "P&E": "Privileges & Elections",
        "C&L": "Commerce & Labor", "HWI": "House Health, Welfare & Inst.", "APP": "House Appropriations",
        "HAPP": "House Appropriations", "FIN": "Senate Finance & Appropriations", "JUD": "Courts of Justice",
        "GL": "General Laws", "AG": "Agriculture", "TRAN": "Transportation",
        "SFIN": "Senate Finance & Appropriations", "HFIN": "House Finance", "SEH": "Senate Education & Health",
        "CL": "Commerce & Labor", "SCL": "Senate Commerce & Labor", "HCL": "House Commerce & Labor"
    }
    
    upper_name = name.upper()
    if upper_name in mapping: return mapping[upper_name]
    
    if name.lower() == "education": return "Education"

    is_senate = "SENATE" in upper_name
    is_house = "HOUSE" in upper_name

    base_name = name
    standard_committees = [
        "Education and Health", "Education", "Commerce and Labor", "General Laws", "Transportation",
        "Finance", "Appropriations", "Courts of Justice", "Privileges and Elections",
        "Agriculture", "Rules", "Local Government", "Public Safety", "Counties Cities and Towns",
        "Health, Welfare and Institutions", "Rehabilitation and Social Services"
    ]
    
    for std in standard_committees:
        if std.lower() in name.lower():
            base_name = std
            break
    
    if "Senate" in base_name or "House" in base_name: return base_name
    if is_senate: return f"Senate {base_name}"
    if is_house: return f"House {base_name}"
    if "Health, Welfare" in base_name: return f"House {base_name}"
    if "Rehabilitation" in base_name: return f"Senate {base_name}"
    if "Education and Health" in base_name: return f"Senate {base_name}"

    return base_name.title()

def clean_status_text(text):
    if not text: return ""
    text = str(text)
    replacements = {
        "HED": "House Education", "HAPP": "House Appropriations", "sub:": "Subcommittee:",
        "P&E": "Privileges & Elections", "C&L": "Commerce & Labor",
        "floor offered": "Floor Amendment Offered", "passed by indefinitely": "Passed By Indefinitely (Dead)"
    }
    for abbr, full in replacements.items():
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        text = pattern.sub(full, text)
    return text

# --- WEB SCRAPER ---
@st.cache_data(ttl=600)
def fetch_schedule_from_web():
    schedule_map = {}
    debug_log = [] 
    headers = {'User-Agent': 'Mozilla/5.0'}

    # SENATE
    try:
        url_senate = "https://apps.senate.virginia.gov/Senator/ComMeetings.php"
        resp = requests.get(url_senate, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if "2026" in line: 
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[AP]M|noon|upon\s+adjourn|\d+\s+minutes?\s+after)', line, re.IGNORECASE)
                if time_match:
                    time_val = time_match.group(0).upper()
                    try:
                        clean_line = line.split("-")[0].replace("–", "-").split("-")[0].strip()
                        clean_line = clean_line.replace("1st", "1").replace("2nd", "2").replace("3rd", "3").replace("th", "")
                        dt = datetime.strptime(clean_line, "%A, %B %d, %Y")
                        date_str = dt.strftime("%Y-%m-%d")
                        if i > 0:
                            comm_name = lines[i-1]
                            if "Cancelled" in comm_name: continue
                            def normalize_text_strict(t):
                                if pd.isna(t): return ""
                                t = str(t).lower().replace('&','and').replace('.','').replace(',','').replace('-',' ')
                                return " ".join(t.split())
                            clean_name = normalize_text_strict(comm_name)
                            if "senate" not in clean_name and "house" not in clean_name: clean_name = "senate " + clean_name 
                            clean_name = clean_name.replace("senate", "").replace("house", "").strip()
                            key = (date_str, clean_name)
                            schedule_map[key] = (time_val, comm_name) 
                    except: pass
    except: pass

    # HOUSE
    try:
        url_house = "https://house.vga.virginia.gov/schedule/meetings"
        resp = requests.get(url_house, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
        current_date_str = None
        for i, line in enumerate(lines):
            if "JANUARY" in line.upper() or "FEBRUARY" in line.upper():
                try:
                    date_text = line if "2026" in line else f"{line}, 2026"
                    date_text = date_text.replace("THURSDAY,", "THURSDAY").strip()
                    match = re.search(r'([A-Z]+ \d{1,2}, 2026)', date_text, re.IGNORECASE)
                    if match:
                        dt = datetime.strptime(match.group(0), "%B %d, %Y")
                        current_date_str = dt.strftime("%Y-%m-%d")
                        continue
                except: pass
            if not current_date_str: continue

            time_match = re.search(r'^(\d{1,2}:\d{2}\s*[AP]M|Noon)', line, re.IGNORECASE)
            if time_match:
                time_val = time_match.group(0)
                if i > 0:
                    comm_name = lines[i-1]
                    if "," in comm_name or "View Agenda" in comm_name:
                        if i > 1:
                            prev_prev = lines[i-2]
                            if len(prev_prev) > 4: comm_name = prev_prev
                    if "New Meeting" in comm_name: continue
                    def normalize_text_strict(t):
                        if pd.isna(t): return ""
                        t = str(t).lower().replace('&','and').replace('.','').replace(',','').replace('-',' ')
                        return " ".join(t.split())
                    clean_name = normalize_text_strict(comm_name)
                    if "senate" not in clean_name and "house" not in clean_name: clean_name = "house " + clean_name 
                    clean_name = clean_name.replace("senate", "").replace("house", "").strip()
                    key = (current_date_str, clean_name)
                    schedule_map[key] = (time_val, comm_name)
    except: pass
    
    st.session_state['debug_data'] = {"map_keys": list(schedule_map.keys()), "log": debug_log}
    return schedule_map

# --- DATA FETCHING (DIRECT FROM LIS) ---
@st.cache_data(ttl=300) 
def fetch_lis_data():
    data = {}
    
    # 1. Fetch Basic Bill Info
    try:
        try: df = pd.read_csv(LIS_BILLS_CSV, encoding='ISO-8859-1')
        except: df = pd.read_csv(LIS_BILLS_CSV.replace(".CSV", ".csv"), encoding='ISO-8859-1')
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
        # Prioritize 'bill_id' (SB160)
        if 'bill_id' in df.columns:
            df['bill_clean'] = df['bill_id'].astype(str).str.upper().str.replace(" ", "").str.strip()
        elif 'bill_number' in df.columns:
             df['bill_clean'] = df['bill_number'].astype(str).str.upper().str.replace(" ", "").str.strip()
        data['bills'] = df
    except: data['bills'] = pd.DataFrame()

    # 2. Fetch Detailed History
    try:
        try: df_hist = pd.read_csv(LIS_HISTORY_CSV, encoding='ISO-8859-1')
        except: df_hist = pd.read_csv(LIS_HISTORY_CSV.replace(".CSV", ".csv"), encoding='ISO-8859-1')
        df_hist.columns = df_hist.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
        
        # Match logic for History file
        hist_bill_col = next((c for c in df_hist.columns if "bill_id" in c), None) # Try ID first
        if not hist_bill_col:
            hist_bill_col = next((c for c in df_hist.columns if "number" in c), None) # Fallback

        if hist_bill_col:
            df_hist['bill_clean'] = df_hist[hist_bill_col].astype(str).str.upper().str.replace(" ", "").str.strip()
            data['history'] = df_hist
        else:
            data['history'] = pd.DataFrame()
    except: 
        data['history'] = pd.DataFrame()

    # 3. Fetch Calendar/Schedules
    calendar_dfs = []
    for url, type_label in [(LIS_SUBDOCKET_CSV, "Subcommittee"), (LIS_DOCKET_CSV, "Committee"), (LIS_CALENDAR_CSV, "Floor")]:
        try:
            try: df = pd.read_csv(url, encoding='ISO-8859-1')
            except: df = pd.read_csv(url.replace(".CSV", ".csv"), encoding='ISO-8859-1')
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
            col = next((c for c in df.columns if "bill" in c), None)
            if col:
                df['bill_clean'] = df[col].astype(str).str.upper().str.replace(" ", "").str.strip()
                df['event_type'] = type_label
                calendar_dfs.append(df)
        except: pass

    if calendar_dfs:
        data['schedule'] = pd.concat(calendar_dfs, ignore_index=True)
    else:
        data['schedule'] = pd.DataFrame()

    return data

def get_bill_data_batch(bill_numbers, lis_data_dict):
    lis_df = lis_data_dict.get('bills', pd.DataFrame())
    history_df = lis_data_dict.get('history', pd.DataFrame())

    results = []
    clean_bills = list(set([str(b).strip().upper().replace(" ", "") for b in bill_numbers if str(b).strip() != 'nan']))
    
    lis_lookup = {}
    if not lis_df.empty and 'bill_clean' in lis_df.columns:
        lis_lookup = lis_df.set_index('bill_clean').to_dict('index')

    history_lookup = {}
    if not history_df.empty and 'bill_clean' in history_df.columns:
        for b_id, group in history_df.groupby('bill_clean'):
            history_lookup[b_id] = group.to_dict('records')

    for bill_num in clean_bills:
        item = lis_lookup.get(bill_num)
        
        title = "Unknown"
        status = "Not Found"
        date_val = ""
        curr_comm = "-"
        curr_sub = "-"
        history_data = []

        if item:
            title = item.get('bill_description', 'No Title')
            status = item.get('last_house_action', '')
            if pd.isna(status) or str(status).strip() == '': 
                status = item.get('last_senate_action', 'Introduced')
            
            date_val = str(item.get('last_house_action_date', ''))
            if not date_val or date_val == 'nan':
                date_val = str(item.get('last_senate_action_date', ''))

        # --- PROCESS HISTORY (Fixed Column Names) ---
        raw_history = history_lookup.get(bill_num, [])
        if raw_history:
            for h_row in raw_history:
                # 1. Get Description
                desc = ""
                for col in ['history_description', 'description', 'action', 'history', 'event']:
                    if col in h_row:
                        desc = str(h_row[col])
                        break
                # 2. Get Date
                date_h = ""
                for col in ['history_date', 'date', 'action_date']:
                    if col in h_row:
                        date_h = str(h_row[col])
                        break
                
                if desc:
                    history_data.append({"Date": date_h, "Action": desc})

                    # 3. Detect Committee
                    desc_lower = desc.lower()
                    if "referred to" in desc_lower and "committee" in desc_lower:
                        match = re.search(r'(?:committee(?:\s+on)?)\s+([a-z\s&,]+)', desc_lower)
                        if match:
                            found_name = match.group(1).title().strip()
                            if "Minutes" not in found_name: curr_comm = found_name
                    elif "referred to" in desc_lower:
                         match = re.search(r'referred to\s+([a-z\s&,]+)', desc_lower)
                         if match:
                             candidate = match.group(1).title().strip()
                             candidate = candidate.replace("Committee On", "").replace("Committee", "").strip()
                             if len(candidate) > 3 and "Minutes" not in candidate:
                                 curr_comm = candidate

                    # 4. Detect Subcommittee
                    if "sub:" in desc_lower:
                        try:
                            parts = desc_lower.split("sub:")
                            curr_sub = parts[1].strip().title()
                        except: pass
        
        # Fallback to columns
        if curr_comm == "-":
            potential_cols = ['last_house_committee', 'last_senate_committee', 'house_committee', 'senate_committee']
            if item:
                for col in potential_cols:
                    val = item.get(col)
                    if pd.notna(val) and str(val).strip() not in ['nan', '', '-', '0']:
                        curr_comm = str(val).strip()
                        break
        
        curr_comm = clean_committee_name(curr_comm)
        
        # Add Chamber Prefix
        if curr_comm and "Senate" not in curr_comm and "House" not in curr_comm:
             if bill_num.startswith("SB") or bill_num.startswith("SJ") or bill_num.startswith("SR"):
                 curr_comm = f"Senate {curr_comm}"
             elif bill_num.startswith("HB") or bill_num.startswith("HJ") or bill_num.startswith("HR"):
                 curr_comm = f"House {curr_comm}"

        lifecycle = determine_lifecycle(str(status), str(curr_comm))

        results.append({
            "Bill Number": bill_num,
            "Official Title": title,
            "Status": str(status),
            "Date": date_val, 
            "Lifecycle": lifecycle,
            "Auto_Folder": get_smart_subject(title),
            "History_Data": history_data[::-1], 
            "Current_Committee": str(curr_comm).strip(),
            "Current_Sub": str(curr_sub).strip()
        })

    if not results: return pd.DataFrame()
    return pd.DataFrame(results)

# --- UI COMPONENTS ---
def render_bill_card(row):
    if row.get('Official Title') not in ["Unknown", "Error", "Not Found", None]:
        display_title = row['Official Title']
    else:
        display_title = row.get('My Title', 'No Title Provided')
    st.markdown(f"**{row['Bill Number']}**")
    
    my_status = str(row.get('My Status', '')).strip()
    if my_status and my_status != 'nan' and my_status != '-':
        st.info(f"🏷️ **Status:** {my_status}")
    
    st.caption(f"{display_title}")
    st.caption(f"_{clean_status_text(row.get('Status'))}_")
    st.divider()

def render_master_list_item(df):
    if df.empty:
        st.caption("No bills.")
        return
    for i, row in df.iterrows():
        header_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', '')
        
        my_status = str(row.get('My Status', '')).strip()
        label_text = f"{row['Bill Number']}"
        if my_status and my_status != 'nan' and my_status != '-':
            label_text += f" - {my_status}"
        if header_title:
             label_text += f" - {header_title}"
        
        with st.expander(label_text):
            st.markdown(f"**🏛️ Current Committee:** {clean_committee_name(row.get('Current_Committee', '-'))}")
            if row.get('Current_Sub') and row.get('Current_Sub') != '-':
                st.markdown(f"**↳ Subcommittee:** {row.get('Current_Sub')}")
                
            st.markdown(f"**📌 Designated Title:** {row.get('My Title', '-')}")
            st.markdown(f"**📜 Official Title:** {row.get('Official Title', '-')}")
            st.markdown(f"**🔄 Status:** {clean_status_text(row.get('Status', '-'))}")
            
            hist_data = row.get('History_Data', [])
            if isinstance(hist_data, list) and hist_data:
                st.markdown("**📜 History:**")
                st.dataframe(pd.DataFrame(hist_data), hide_index=True, use_container_width=True)
            else:
                st.caption(f"Date: {row.get('Date', '-')}")

            lis_link = f"https://lis.virginia.gov/bill-details/20261/{row['Bill Number']}"
            st.markdown(f"🔗 [View Official Bill on LIS]({lis_link})")

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")
est = pytz.timezone('US/Eastern')
current_time_est = datetime.now(est).strftime("%I:%M %p EST")

if 'last_run' not in st.session_state:
    st.session_state['last_run'] = current_time_est

# --- SIDEBAR CONTROLS ---
demo_mode = st.sidebar.checkbox("🛠️ Enable Demo Mode", value=False)
col_btn, col_time = st.columns([1, 6])

with col_btn:
    if st.button("🔄 Check for Updates"):
        st.session_state['last_run'] = datetime.now(est).strftime("%I:%M %p EST")
        st.cache_data.clear() 
        st.rerun()

with col_time:
    st.markdown(f"**Last Refreshed:** `{st.session_state['last_run']}`")

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
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper().str.replace(" ", "")
    sheet_df = sheet_df[sheet_df['Bill Number'] != 'NAN']
    sheet_df = sheet_df.drop_duplicates(subset=['Bill Number'])
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")
    if 'My Status' not in sheet_df.columns: sheet_df['My Status'] = "-"

except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# 2. FETCH LIS DATA
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()

# 2b. FETCH WEB SCHEDULE
web_schedule_map = fetch_schedule_from_web()

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
    
    def assign_folder(row):
        title_to_check = row.get('Official Title', '')
        if str(title_to_check) in ["Unknown", "Error", "Not Found", "nan", "None", ""]:
            title_to_check = row.get('My Title', '')
        return get_smart_subject(str(title_to_check))

    if 'Auto_Folder' not in final_df.columns or final_df['Auto_Folder'].isnull().any():
         final_df['Auto_Folder'] = final_df.apply(assign_folder, axis=1)

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
                        for _, row in bills_in_folder.iterrows():
                            render_bill_card(row)
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            
            in_comm = subset[subset['Lifecycle'] == "📥 In Committee"]
            out_comm = subset[subset['Lifecycle'] == "📣 Out of Committee"]
            passed = subset[subset['Lifecycle'].isin(["✅ Signed & Enacted", "✍️ Awaiting Signature"])]
            failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown("#### 📥 In Committee")
                render_master_list_item(in_comm)
            with m2:
                st.markdown("#### 📣 Out of Committee")
                render_master_list_item(out_comm)
            with m3:
                st.markdown("#### 🎉 Passed")
                render_master_list_item(passed)
            with m4:
                st.markdown("#### ❌ Failed")
                render_master_list_item(failed)

    # --- TAB 3: RESTORED STRICT DOCKET CHECK ---
    with tab_upcoming:
        st.subheader("📅 Your Confirmed Agenda")
        today = datetime.now(est).date()
        cols = st.columns(7)
        
        schedule_df = lis_data.get('schedule', pd.DataFrame())
        my_bills_clean = [b.upper().strip() for b in bills_to_track]
        
        # STRICT FILTER: Must exist in LIS Dockets
        confirmed_bills_set = set()
        if not schedule_df.empty:
            matches = schedule_df[schedule_df['bill_clean'].isin(my_bills_clean)]
            confirmed_bills_set = set(matches['bill_clean'].unique())
            
        bill_info_map = final_df.set_index('Bill Number')[['Current_Committee', 'Current_Sub', 'My Status', 'Status']].to_dict('index')

        for i in range(7):
            target_date = today + timedelta(days=i)
            target_date_str = target_date.strftime('%Y-%m-%d')
            display_date_str = target_date.strftime("%a %m/%d")
            
            with cols[i]:
                st.markdown(f"**{display_date_str}**")
                st.divider()
                
                events_found = False
                bills_shown_today = set()

                todays_meetings = {k[1]: v for k, v in web_schedule_map.items() if k[0] == target_date_str}
                
                if todays_meetings:
                    for scraper_clean_name, (scraper_time, scraper_full_name) in todays_meetings.items():
                        if "caucus" in scraper_full_name.lower(): continue

                        matched_bills = []
                        # STRICT MATCH: Only check Verified Docket Bills
                        for b_id in confirmed_bills_set:
                            if b_id in bills_shown_today: continue 

                            info = bill_info_map.get(b_id, {})
                            def normalize_text_strict(t):
                                if pd.isna(t): return ""
                                t = str(t).lower().replace('&','and').replace('.','').replace(',','').replace('-',' ')
                                return " ".join(t.split())

                            curr_comm = normalize_text_strict(info.get('Current_Committee', ''))
                            curr_sub = normalize_text_strict(info.get('Current_Sub', ''))
                            
                            match = False
                            if curr_comm and len(curr_comm) > 2:
                                if curr_comm in scraper_clean_name or scraper_clean_name in curr_comm:
                                    match = True
                            if curr_sub and len(curr_sub) > 2:
                                if curr_sub in scraper_clean_name or scraper_clean_name in curr_sub:
                                    match = True
                                    
                            if match:
                                matched_bills.append(b_id)
                                bills_shown_today.add(b_id)

                        if matched_bills:
                            events_found = True
                            st.markdown(f"**{clean_committee_name(scraper_full_name)}**")
                            st.caption(f"⏰ {scraper_time}")
                            for b_id in matched_bills:
                                info = bill_info_map.get(b_id, {})
                                status_text = ""
                                raw_status = str(info.get('My Status', '')).strip()
                                if raw_status and raw_status != 'nan' and raw_status != '-':
                                    status_text = f" - {raw_status}"
                                st.error(f"**{b_id}**{status_text}")
                            st.divider()

                if not events_found:
                    st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("All Systems Go?")
        
        hist_cols = st.session_state.get('history_cols', [])
        if hist_cols:
            st.write(f"**History File Columns:**")
            st.code(str(hist_cols))
        else:
            st.write("**History File Columns:** Not loaded")
            
        debug_data = st.session_state.get('debug_data', {})
        keys = debug_data.get('map_keys', [])
        st.write(f"**Scraper Status:** {'🟢 Active' if keys else '🔴 Empty'}")
