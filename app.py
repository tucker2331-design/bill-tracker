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
LIS_DOCKET_CSV = LIS_BASE_URL + "DOCKET.CSV"

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- COMMITTEE CODE MAP ---
COMMITTEE_MAP = {
    "H01": "House Privileges and Elections", "H02": "House Courts of Justice", "H03": "House Education",
    "H04": "House General Laws", "H05": "House Roads and Internal Navigation", "H06": "House Finance",
    "H07": "House Appropriations", "H08": "House Counties, Cities and Towns", "H09": "House Commerce and Labor",
    "H10": "House Health, Welfare and Institutions", "H11": "House Conservation and Natural Resources",
    "H12": "House Agriculture", "H13": "House Militia, Police and Public Safety", "H14": "House Claims",
    "H15": "House Chesapeake and Its Tributaries", "H16": "House Mining and Mineral Resources",
    "H17": "House Corporations, Insurance and Banking", "H18": "House Rules", "H19": "House Nominations and Confirmations",
    "H20": "House Interstate Cooperation", "H21": "House Science and Technology", "H22": "House Courts of Justice",
    "H23": "House Education", "H24": "House Education", "H25": "House Health and Human Services",
    "H26": "House Public Safety", "H27": "House Transportation", "H28": "House Communications, Technology and Innovation",
    "H29": "House Health and Human Services",
    "S01": "Senate Agriculture", "S02": "Senate Commerce and Labor", "S03": "Senate Courts of Justice", 
    "S04": "Senate Education and Health", "S05": "Senate Finance and Appropriations", "S06": "Senate General Laws", 
    "S07": "Senate Local Government", "S08": "Senate Privileges and Elections", "S09": "Senate Rehab", 
    "S10": "Senate Transportation", "S11": "Senate Rules"
}

# --- HELPER FUNCTIONS ---

def get_smart_subject(title):
    return "📂 Unassigned / General" 

def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    clean = re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)
    return clean

def determine_lifecycle(status_text, committee_name, bill_id="", history_text=""):
    status = str(status_text).lower()
    comm = str(committee_name).strip()
    b_id = str(bill_id).upper()
    hist = str(history_text).lower()
    
    # 1. Passed / Enacted Types
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]): return "✅ Signed & Enacted"
    if "vetoed" in status: return "❌ Vetoed"
    
    # 2. Resolutions / Amendments (CHECK HISTORY FOR BOTH CHAMBERS)
    is_resolution = any(prefix in b_id for prefix in ["HJ", "SJ", "HR", "SR"])
    if is_resolution:
        # Single Chamber Resolutions (HR/SR) - Pass if agreed to
        if b_id.startswith("HR") or b_id.startswith("SR"):
            if "agreed to" in status or "agreed to" in hist: return "✅ Passed (Resolution)"
        
        # Joint Resolutions (HJ/SJ) - Must pass BOTH
        if b_id.startswith("HJ"):
            # Needs Senate Agreement
            if "agreed to by senate" in hist or "passed senate" in hist: return "✅ Passed (Resolution)"
        elif b_id.startswith("SJ"):
            # Needs House Agreement
            if "agreed to by house" in hist or "passed house" in hist: return "✅ Passed (Resolution)"

    # 3. Passed Legislature (Bills needing signature)
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]): return "✍️ Awaiting Signature"
    
    # 4. Dead
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]): return "❌ Dead / Tabled"
    
    # 5. Out of Committee (Intermediate)
    out_keywords = ["reported", "passed", "agreed", "engrossed", "communicated", "reading waived", "read second", "read third"]
    if any(x in status for x in out_keywords): return "📣 Out of Committee"
    
    # 6. In Committee
    if "pending" in status or "prefiled" in status: return "📥 In Committee"
    if comm not in ["-", "nan", "None", "", "Unassigned"] and len(comm) > 2: return "📥 In Committee"
    
    return "📥 In Committee"

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return ""
    name = str(name).strip()
    if name in COMMITTEE_MAP: return COMMITTEE_MAP[name]
    if name.startswith("H-") or name.startswith("S-") or name.startswith("h-") or name.startswith("s-"): name = name[2:]
    name = re.sub(r'\b[A-Z][a-z]+, [A-Z]\. ?[A-Z]?\.?.*$', '', name) 
    name = re.sub(r'\b(Simon|Rasoul|Willett|Helmer|Lucas|Surovell|Locke|Deeds|Favola|Marsden|Ebbin|McPike|Hayes|Carroll Foy|Subcommittee #\d+)\b.*', '', name, flags=re.IGNORECASE)
    name = name.replace("Committee For", "").replace("Committee On", "").replace("Committee", "").strip()
    return name.title()

def clean_status_text(text):
    if not text: return ""
    text = str(text)
    return text.replace("HED", "House Education").replace("sub:", "Subcommittee:")

def extract_vote_info(status_text):
    match = re.search(r'\((\d{1,3}-Y \d{1,3}-N)\)', str(status_text))
    if match: return match.group(1)
    return None

# --- LAST RESORT SCRAPER (DISABLED) ---
@st.cache_data(ttl=3600)
def scrape_committee_from_bill_page(bill_number):
    return None # Disabled for speed

# --- 1. HTML SCRAPER (CALENDAR) ---
@st.cache_data(ttl=600)
def fetch_html_calendar():
    calendar_times = {'NO_DATE': {}}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # HOUSE
    try:
        url = "https://house.vga.virginia.gov/schedule/meetings"
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
            curr_date = None
            for i, line in enumerate(lines):
                date_match = re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Z][a-z]+)\s+(\d{1,2})', line)
                if date_match:
                    try:
                        dt = datetime.strptime(f"{date_match.group(2)} {date_match.group(3)} 2026", "%B %d %Y")
                        curr_date = dt.strftime("%Y-%m-%d")
                    except: pass
                if curr_date:
                    time_match = re.search(r'^\d{1,2}:\d{2}\s*[AP]M', line)
                    text_time_match = "adjournment" in line.lower() or "recess" in line.lower()
                    final_time = time_match.group(0) if time_match else (line if text_time_match else None)
                    if final_time and i > 0 and "Agenda" not in lines[i-1]:
                        clean = clean_committee_name(f"House {lines[i-1]}")
                        if curr_date not in calendar_times: calendar_times[curr_date] = {}
                        key = clean.lower().replace("committee","").replace("house","").replace("senate","").replace("of","").replace("for","").replace("and","").replace("&","").replace(" ","")
                        calendar_times[curr_date][key] = final_time 
    except: pass

    # SENATE
    try:
        url = "https://apps.senate.virginia.gov/Senator/ComMeetings.php"
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
            for i, line in enumerate(lines):
                if "2026" in line and "-" in line:
                    try:
                        raw_date_part = line.split("-")[0].strip()
                        d_str = datetime.strptime(raw_date_part, "%A, %B %d, %Y").strftime("%Y-%m-%d")
                        raw_time_part = "-".join(line.split("-")[1:]).strip()
                        if i > 0 and len(lines[i-1]) > 3:
                            clean = clean_committee_name(f"Senate {lines[i-1]}")
                            if d_str not in calendar_times: calendar_times[d_str] = {}
                            key = clean.lower().replace("committee","").replace("house","").replace("senate","").replace("of","").replace("for","").replace("and","").replace("&","").replace(" ","")
                            calendar_times[d_str][key] = raw_time_part
                    except: pass
    except: pass
    return calendar_times, []

# --- 2. DATA FETCHING ---
@st.cache_data(ttl=60) 
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
        col = next((c for c in data['bills'].columns if c in ['bill_number','bill_id']), None)
        if col: data['bills']['bill_clean'] = data['bills'][col].astype(str).apply(clean_bill_id)

    data['history'] = load_csv(LIS_HISTORY_CSV)
    if not data['history'].empty:
        col = next((c for c in data['history'].columns if c in ['bill_number','bill_id']), None)
        if col: data['history']['bill_clean'] = data['history'][col].astype(str).apply(clean_bill_id)

    data['docket'] = load_csv(LIS_DOCKET_CSV)
    if not data['docket'].empty:
        col = next((c for c in data['docket'].columns if c in ['bill_no','bill_number','bill_id']), None)
        if col: data['docket']['bill_clean'] = data['docket'][col].astype(str).apply(clean_bill_id)
        rename_map = {}
        for c in data['docket'].columns:
            if 'com' in c and 'des' in c: rename_map[c] = 'committee_name'
            if 'date' in c and 'meet' in c: rename_map[c] = 'meeting_date' 
            if 'doc' in c and 'date' in c: rename_map[c] = 'meeting_date'
        data['docket'].rename(columns=rename_map, inplace=True)
        
    return data

def get_bill_data_batch(bill_numbers, lis_data_dict):
    lis_df = lis_data_dict.get('bills', pd.DataFrame())
    history_df = lis_data_dict.get('history', pd.DataFrame())
    docket_df = lis_data_dict.get('docket', pd.DataFrame())
    
    results = []
    clean_bills = list(set([clean_bill_id(b) for b in bill_numbers if str(b).strip() != 'nan']))
    
    lis_lookup = {}
    if not lis_df.empty and 'bill_clean' in lis_df.columns:
        lis_lookup = lis_df.set_index('bill_clean').to_dict('index')

    history_lookup = {}
    if not history_df.empty and 'bill_clean' in history_df.columns:
        for b_id, group in history_df.groupby('bill_clean'):
            history_lookup[b_id] = group.to_dict('records')
            
    docket_lookup = {}
    if not docket_df.empty and 'bill_clean' in docket_df.columns:
        for b_id, group in docket_df.groupby('bill_clean'):
            docket_lookup[b_id] = group.to_dict('records')

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
        history_blob = ""
        if raw_history:
            for h_row in raw_history:
                desc = ""; date_h = ""
                for col in ['history_description', 'description', 'action', 'history']:
                    if col in h_row and pd.notna(h_row[col]): desc = str(h_row[col]); break
                for col in ['history_date', 'date', 'action_date']:
                    if col in h_row and pd.notna(h_row[col]): date_h = str(h_row[col]); break
                if desc:
                    history_data.append({"Date": date_h, "Action": desc})
                    history_blob += desc.lower() + " "
                    desc_lower = desc.lower()
                    if "referred to" in desc_lower:
                        match = re.search(r'referred to (?:committee on|the committee on)?\s?([a-z\s&,-]+)', desc_lower)
                        if match: found = match.group(1).strip().title(); curr_comm = found if len(found) > 3 else curr_comm
                    if "sub:" in desc_lower:
                        try: curr_sub = desc_lower.split("sub:")[1].strip().title()
                        except: pass
        
        # --- SMART LOGIC: Use 'last_actid' Code if Committee Name is Missing ---
        if curr_comm == "-":
            val = item.get('last_house_committee')
            if not val or str(val) == 'nan':
                act_id = str(item.get('last_actid', ''))
                if len(act_id) >= 3:
                    code = act_id[:3]
                    if code in COMMITTEE_MAP: curr_comm = COMMITTEE_MAP[code]
            elif str(val) in COMMITTEE_MAP:
                curr_comm = COMMITTEE_MAP[str(val)]
        
        # --- OVERRIDE: If status says "Pending", it is NOT in a committee yet ---
        if "pending" in str(status).lower() or "prefiled" in str(status).lower():
            if "referred" not in str(status).lower(): 
                curr_comm = "Unassigned"
        
        # --- FIX: SKEPTICAL "COURTS OF JUSTICE" CHECK ---
        if "Courts" in str(curr_comm) and "referred" not in history_blob and "referred" not in str(status).lower():
            curr_comm = "Unassigned"

        curr_comm = clean_committee_name(curr_comm)
        
        # --- PASSED HISTORY TO LIFECYCLE FOR RESOLUTION CHECK ---
        lifecycle = determine_lifecycle(str(status), str(curr_comm), bill_num, history_blob)
        
        display_comm = curr_comm
        if "Passed" in lifecycle or "Signed" in lifecycle or "Awaiting" in lifecycle:
             if "engross" in str(status).lower(): display_comm = "🏛️ Engrossed (Passed Chamber)"
             elif "read" in str(status).lower(): display_comm = "📜 On Floor (Read/Reported)"
             elif "passed" in str(status).lower(): display_comm = "🎉 Passed Chamber"
             else: display_comm = "On Floor / Reported"

        # --- DOCKET MATCHING ---
        upcoming_meetings = []
        raw_docket = docket_lookup.get(bill_num, [])
        for d in raw_docket:
            d_date = d.get('meeting_date') or d.get('doc_date')
            d_comm_raw = str(d.get('committee_name', 'Unknown'))
            if "Passed" in lifecycle or "Signed" in lifecycle: d_comm_raw = "Floor Session / Chamber Action"
            elif d_comm_raw == 'Unknown' or d_comm_raw == 'nan': d_comm_raw = curr_comm

            if d_date:
                try:
                    if "/" in str(d_date): dt_obj = datetime.strptime(str(d_date), "%m/%d/%Y")
                    else: dt_obj = datetime.strptime(str(d_date), "%Y-%m-%d")
                    fmt_date = dt_obj.strftime("%Y-%m-%d")
                    upcoming_meetings.append({"Date": fmt_date, "CommitteeRaw": d_comm_raw})
                except: pass

        results.append({
            "Bill Number": bill_num, "Official Title": title, "Status": str(status), "Date": date_val, 
            "Lifecycle": lifecycle, "Auto_Folder": "📂 Unassigned / General", "History_Data": history_data[::-1], 
            "Current_Committee": str(curr_comm).strip(), "Display_Committee": str(display_comm).strip(), 
            "Current_Sub": str(curr_sub).strip(), "Upcoming_Meetings": upcoming_meetings
        })
    return pd.DataFrame(results) if results else pd.DataFrame()

# --- SLACK BOT ---
def check_and_broadcast(df_bills, df_subscribers, demo_mode):
    st.sidebar.header("🤖 Slack Bot Status")
    if demo_mode: st.sidebar.warning("🛠️ Demo Mode Active"); return
    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token: st.sidebar.error("❌ Disconnected (Token Missing)"); return
    client = WebClient(token=token)
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
        if not subscriber_list: st.sidebar.warning("⚠️ No Subscribers Found"); return
        user_id = client.users_lookupByEmail(email=subscriber_list[0].strip())['user']['id']
        history = client.conversations_history(channel=client.conversations_open(users=[user_id])['channel']['id'], limit=100)
        raw_history_text = "\n".join([m.get('text', '') for m in history['messages']])
        history_text = raw_history_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        st.sidebar.success(f"✅ Connected to Slack")
    except Exception as e: st.sidebar.error(f"❌ Slack Error: {e}"); return
    
    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n_Latest changes detected:_\n"
    updates_found = False
    for i, row in df_bills.iterrows():
        if "LIS Connection Error" in str(row.get('Status')): continue
        b_num = str(row['Bill Number']).strip(); raw_status = str(row.get('Status', 'No Status')).strip(); clean_status = clean_status_text(raw_status)
        if b_num in history_text and clean_status in history_text: continue
        display_name = str(row.get('My Title', '-'))
        if display_name == "-" or display_name == "nan" or not display_name: official = str(row.get('Official Title', '')); display_name = (official[:60] + '..') if len(official) > 60 else official
        updates_found = True
        report += f"\n⚪ *{b_num}* | {display_name}\n> _{clean_status}_\n"
    
    if updates_found:
        st.toast(f"📢 Sending updates..."); 
        for email in subscriber_list:
            try: uid = client.users_lookupByEmail(email=email.strip())['user']['id']; client.chat_postMessage(channel=uid, text=report)
            except: pass
        st.toast("✅ Sent!"); st.sidebar.info("🚀 New Update Sent!")
    else: st.sidebar.info("💤 No new updates needed.")

# --- UI RENDERERS ---
def render_bill_card(row):
    title = row.get('Official Title', 'No Title')
    if title in ["Unknown", "Error", None]: title = row.get('My Title', 'No Title')
    st.markdown(f"**{row['Bill Number']}**")
    my_status = str(row.get('My Status', '')).strip()
    if my_status and my_status != 'nan' and my_status != '-': st.info(f"🏷️ **Status:** {my_status}")
    st.caption(f"{title}"); st.caption(f"_{clean_status_text(row.get('Status'))}_"); st.divider()

def render_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    def rename_unassigned(name):
        name = str(name).strip()
        if name in ['-', 'nan', 'None', '', '0', 'Unassigned']: return "Unassigned"
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

# --- NEW: PASSED BILL GROUPER ---
def render_passed_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    g_signed = df[df['Lifecycle'] == "✅ Signed & Enacted"]
    g_vetoed = df[df['Lifecycle'] == "❌ Vetoed"]
    g_res = df[df['Lifecycle'] == "✅ Passed (Resolution)"]
    g_awaiting = df[df['Lifecycle'] == "✍️ Awaiting Signature"]
    
    if not g_signed.empty: 
        st.markdown("##### ✅ Signed & Enacted")
        for i, r in g_signed.iterrows(): _render_single_bill_row(r)
    if not g_awaiting.empty:
        st.markdown("##### ✍️ Awaiting Signature")
        for i, r in g_awaiting.iterrows(): _render_single_bill_row(r)
    if not g_res.empty:
        st.markdown("##### 📜 Resolution / Amendment (Passed)")
        for i, r in g_res.iterrows(): _render_single_bill_row(r)
    if not g_vetoed.empty:
        st.markdown("##### ❌ Vetoed")
        for i, r in g_vetoed.iterrows(): _render_single_bill_row(r)

def render_simple_list_item(df):
    if df.empty: st.caption("No bills."); return
    for i, row in df.iterrows(): _render_single_bill_row(row)

def _render_single_bill_row(row):
    title = row.get('Official Title', 'No Title')
    if title in ["Unknown", "Error", None]: title = row.get('My Title', 'No Title')
    my_status = str(row.get('My Status', '')).strip()
    label_text = f"{row['Bill Number']}"
    if my_status and my_status != 'nan' and my_status != '-': label_text += f" - {my_status}"
    if title: label_text += f" - {title}"
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

# 2. FETCH DATA & SCRAPER
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()
scraped_times, scrape_log = fetch_html_calendar() # Run CORRECTED smart scraper

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
    
    # Auto Topic Folder
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
    def get_subject(row):
        txt = str(row.get('Official Title', '')) + " " + str(row.get('My Title', ''))
        txt = txt.lower()
        for cat, keys in TOPIC_KEYWORDS.items():
            if any(k in txt for k in keys): return cat
        return "📂 Unassigned / General"
    final_df['Auto_Folder'] = final_df.apply(get_subject, axis=1)

    check_and_broadcast(final_df, subs_df, demo_mode)

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
            passed = subset[subset['Lifecycle'].isin(["✅ Signed & Enacted", "✍️ Awaiting Signature", "✅ Passed (Resolution)", "❌ Vetoed"])]
            failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown("#### 📥 In Committee"); render_grouped_list_item(in_comm)
            with m2: st.markdown("#### 📣 Out of Committee"); render_simple_list_item(out_comm)
            with m3: st.markdown("#### 🎉 Passed"); render_passed_grouped_list_item(passed)
            with m4: st.markdown("#### ❌ Failed"); render_simple_list_item(failed)

    # --- TAB 3: CALENDAR (DOCKET FILE + SCAPER) ---
    with tab_upcoming:
        st.subheader("📅 Your Confirmed Agenda")
        today = datetime.now(est).date()
        cols = st.columns(7)
        
        # Build Calendar Map
        calendar_map = {}
        for _, row in final_df.iterrows():
            meetings = row.get('Upcoming_Meetings', [])
            if isinstance(meetings, list):
                for m in meetings:
                    m_date_str = str(m['Date']).split(" ")[0]
                    m_comm_raw = m.get('CommitteeRaw', 'Unknown')
                    
                    b_id = row['Bill Number']
                    clean_name = clean_committee_name(m_comm_raw)
                    if "Senate" not in clean_name and "House" not in clean_name:
                        if b_id.startswith("HB") or b_id.startswith("HJ") or b_id.startswith("HR"): clean_name = f"House {clean_name}"
                        elif b_id.startswith("SB") or b_id.startswith("SJ") or b_id.startswith("SR"): clean_name = f"Senate {clean_name}"
                            
                    try:
                        if "/" in m_date_str: d_obj = datetime.strptime(m_date_str, "%m/%d/%Y").date()
                        else: d_obj = datetime.strptime(m_date_str, "%Y-%m-%d").date()
                        formatted_date = d_obj.strftime("%Y-%m-%d")
                        
                        if formatted_date not in calendar_map: calendar_map[formatted_date] = {}
                        if clean_name not in calendar_map[formatted_date]: calendar_map[formatted_date][clean_name] = []
                        calendar_map[formatted_date][clean_name].append(row)
                    except: pass

        for i in range(7):
            target_date = today + timedelta(days=i)
            target_date_str = target_date.strftime('%Y-%m-%d')
            display_date_str = target_date.strftime("%a %m/%d")
            with cols[i]:
                st.markdown(f"**{display_date_str}**")
                st.divider()
                
                # SECTION 1: UPCOMING MEETINGS (FROM DOCKET)
                if target_date_str in calendar_map:
                    for comm_name, bills in calendar_map[target_date_str].items():
                        # RAW SEARCH MATCHING (Keyword Intersection)
                        time_display = "Time TBA"
                        
                        # TRY EXACT DATE FIRST
                        if target_date_str in scraped_times:
                            docket_words = set(comm_name.lower().replace("house","").replace("senate","").replace("committee","").split())
                            docket_words.discard("of"); docket_words.discard("for"); docket_words.discard("and"); docket_words.discard("&"); docket_words.discard("-")
                            docket_words = {w for w in docket_words if len(w) > 3}
                            if docket_words:
                                for s_key, s_time in scraped_times[target_date_str].items():
                                    if any(w in s_key.lower() for w in docket_words):
                                        time_display = s_time
                                        break
                        
                        st.markdown(f"**{comm_name}**")
                        st.caption(f"⏰ {time_display}")
                        for row in bills: _render_single_bill_row(row)
                        st.divider()

                # SECTION 2: COMPLETED ACTIONS (TODAY ONLY)
                if i == 0:
                    events_found = False
                    for _, row in final_df.iterrows():
                        if target_date_str in calendar_map:
                            is_dup = False
                            for c_list in calendar_map[target_date_str].values():
                                if row['Bill Number'] in [r['Bill Number'] for r in c_list]: is_dup = True
                            if is_dup: continue

                        last_date = str(row.get('Date', ''))
                        is_today = False
                        try:
                            if "/" in last_date: lis_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
                            else: lis_dt = datetime.strptime(last_date, "%Y-%m-%d").date()
                            if lis_dt == target_date: is_today = True
                        except: pass
                        
                        if is_today:
                            lis_status = str(row.get('Status', '')).lower()
                            if any(x in lis_status for x in ["reported", "passed", "defeat", "stricken", "agreed", "read", "engross", "vote"]):
                                if not events_found: 
                                    st.caption("🏁 **Completed Today**")
                                    events_found = True
                                
                                my_status = str(row.get('My Status', '')).strip() 
                                vote_str = extract_vote_info(row.get('Status', ''))
                                
                                label_text = f"{row['Bill Number']}"
                                if vote_str: label_text += f" **PASSED {vote_str}**"
                                elif my_status != '-' and my_status != 'nan': label_text += f" - {my_status}"
                                
                                with st.expander(label_text):
                                    st.markdown(f"**🏛️ Current Status:** {row.get('Display_Committee', '-')}")
                                    st.markdown(f"**📌 Designated Title:** {row.get('My Title', '-')}")
                                    st.markdown(f"**🔄 Status:** {clean_status_text(row.get('Status', '-'))}")
                                    
                                    hist_data = row.get('History_Data', [])
                                    if isinstance(hist_data, list) and hist_data:
                                        st.markdown("**📜 History:**")
                                        st.dataframe(pd.DataFrame(hist_data), hide_index=True, use_container_width=True)
                                    
                                    lis_link = f"https://lis.virginia.gov/bill-details/20261/{row['Bill Number']}"
                                    st.markdown(f"🔗 [View Official Bill on LIS]({lis_link})")

                if not (target_date_str in calendar_map) and (i != 0 or not events_found):
                    st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("System Status:")
        if 'docket' in lis_data and not lis_data['docket'].empty:
             st.write(f"**Docket File:** 🟢 Loaded ({len(lis_data['docket'])} rows)")
        else:
             st.write(f"**Docket File:** 🔴 Not Found")
        
        st.write("**Scraper Log (First 10):**")
        st.text("\n".join(scrape_log[:10]))
