import streamlit as st
import pandas as pd
import requests
import re
import json
import time
from datetime import datetime, timedelta
import pytz
from slack_sdk import WebClient
from bs4 import BeautifulSoup 
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- NATIVE AUTO-REFRESH (The 5-Minute Heartbeat) ---
st_autorefresh(interval=300000, limit=None, key="lobbyist_auto_sync")

MANUAL_SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
BILLS_URL = f"https://docs.google.com/spreadsheets/d/{MANUAL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
SUBS_URL = f"https://docs.google.com/spreadsheets/d/{MANUAL_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Subscribers"
MASTERMIND_SHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"
MASTERMIND_URL = f"https://docs.google.com/spreadsheets/d/{MASTERMIND_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"
BUG_LOGS_URL = f"https://docs.google.com/spreadsheets/d/{MASTERMIND_SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bug_Logs"

GITHUB_OWNER, GITHUB_REPO, WORKFLOW_FILENAME = "tucker2331-design", "bill-tracker", "update_database.yml"

COMMITTEE_MAP = {
    "H01": "House Privileges and Elections", "H02": "House Courts of Justice", "H03": "House Education",
    "H04": "House General Laws", "H05": "House Roads and Internal Navigation", "H06": "House Finance",
    "H07": "House Appropriations", "H08": "House Counties, Cities and Towns", 
    "H10": "House Health, Welfare and Institutions", "H11": "House Conservation and Natural Resources",
    "H12": "House Agriculture", "H13": "House Militia, Police and Public Safety", 
    "H14": "House Labor and Commerce", "S01": "Senate Agriculture", "S02": "Senate Commerce and Labor", 
    "S03": "Senate Courts of Justice", "S04": "Senate Education and Health", "S05": "Senate Finance and Appropriations", 
    "S06": "Senate General Laws", "S07": "Senate Local Government", "S08": "Senate Privileges and Elections", 
    "S09": "Senate Rehab", "S10": "Senate Transportation", "S11": "Senate Rules"
}

# --- SURGERY 1: THE TRUTH CLOCK ---
# Pings the GitHub API to find the exact time the database was actually updated
@st.cache_data(ttl=60, show_spinner=False)
def get_last_sync_time():
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILENAME}/runs?status=success&per_page=1"
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token: headers["Authorization"] = f"Bearer {token}"
        
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200:
            runs = r.json().get("workflow_runs", [])
            if runs:
                # GitHub returns UTC. Convert to EST.
                utc_time = datetime.strptime(runs[0]["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
                return utc_time.astimezone(pytz.timezone('US/Eastern')).strftime("%I:%M %p EST")
    except: pass
    return "Syncing..."

def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    return re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', str(bill_text).upper().replace(" ", "").strip())

def clean_committee_name(name):
    if not name or str(name).lower() == 'nan': return ""
    name = str(name).strip()
    if name in COMMITTEE_MAP: return COMMITTEE_MAP[name]
    name = re.sub(r'\b(Simon|Rasoul|Willett|Helmer|Lucas|Surovell|Locke|Deeds|Favola|Marsden|Ebbin|McPike|Hayes|Carroll Foy)\b.*', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\(?Subcommittee:.*?\)?', '', name, flags=re.IGNORECASE)
    name = name.replace("Committee For", "").replace("Committee On", "").replace("Committee", "").strip()
    if name.startswith("H") and name[1].isupper() and not name.startswith("House"): name = "House " + name[1:]
    if name.startswith("S") and name[1].isupper() and not name.startswith("Senate"): name = "Senate " + name[1:]
    return name.title()

def clean_status_text(text): return str(text).replace("HED", "House Education").replace("sub:", "Subcommittee:") if text else ""

def extract_vote_info(status_text):
    match = re.search(r'\((\d{1,3}-Y \d{1,3}-N)\)', str(status_text))
    return match.group(1) if match else None

def get_clean_sub_name(raw_sub):
    sub = str(raw_sub).strip()
    if sub in ['-', 'nan', 'None', '', 'Unassigned']: return '-'
    sub = re.sub(r'\(\s*\d+-Y\s+\d+-N.*?\)', '', sub, flags=re.IGNORECASE).strip()
    return re.sub(r'(?i)\s+(recommends|reports|failed|assigned|passed|continued).*', '', sub).strip() or '-'

@st.cache_data(ttl=300, show_spinner=False)
def load_databases(time_block_key):
    try:
        cb = int(time.time())
        live_master_url = f"{MASTERMIND_URL}&cb={cb}"
        live_manual_url = f"{BILLS_URL}&cb={cb}"
        live_bugs_url = f"{BUG_LOGS_URL}&cb={cb}"

        df_master = pd.read_csv(live_master_url)
        if 'History_Data' in df_master.columns: df_master['History_Data'] = df_master['History_Data'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
        if 'Upcoming_Meetings' in df_master.columns: df_master['Upcoming_Meetings'] = df_master['Upcoming_Meetings'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
        
        try: df_bugs = pd.read_csv(live_bugs_url)
        except: df_bugs = pd.DataFrame()

        raw_manual = pd.read_csv(live_manual_url)
        raw_manual.columns = raw_manual.columns.str.strip()
        
        cols_w = ['Bills Watching', 'Title (Watching)']
        if 'Status (Watching)' in raw_manual.columns: cols_w.append('Status (Watching)')
        df_w = raw_manual[cols_w].copy().dropna(subset=['Bills Watching'])
        df_w.columns = ['Bill Number', 'My Title'] + (['My Status'] if 'Status (Watching)' in raw_manual.columns else [])
        df_w['Type'] = 'Watching'

        w_col_name = next((c for c in raw_manual.columns if "Working On" in c and "Title" not in c and "Status" not in c), None)
        df_i = pd.DataFrame()
        if w_col_name:
            cols_i = [w_col_name]
            title_work_col = next((c for c in raw_manual.columns if "Title (Working)" in c), None)
            if title_work_col: cols_i.append(title_work_col)
            status_work_col = next((c for c in raw_manual.columns if "Status (Working)" in c), None)
            if status_work_col: cols_i.append(status_work_col)
            df_i = raw_manual[cols_i].copy().dropna(subset=[w_col_name])
            df_i.columns = ['Bill Number'] + (['My Title'] if title_work_col else []) + (['My Status'] if status_work_col else [])
            df_i['Type'] = 'Involved'
        
        df_team = pd.concat([df_w, df_i], ignore_index=True).assign(**{'Bill Number': lambda x: x['Bill Number'].apply(clean_bill_id)}).drop_duplicates(subset=['Bill Number'])
        if 'My Title' not in df_team.columns: df_team['My Title'] = "-"
        df_team['My Title'] = df_team['My Title'].fillna("-")
        if 'My Status' not in df_team.columns: df_team['My Status'] = "-"

        final_df = pd.merge(df_team, df_master, on="Bill Number", how="left")
        final_df['Auto_Folder'] = final_df['Auto_Folder'].fillna("📂 Unassigned / General")
        final_df['Lifecycle'] = final_df['Lifecycle'].fillna("📥 In Committee")
        final_df['Is_Youth'] = final_df['Is_Youth'].fillna("False").astype(str) == "True"
        
        return final_df, df_master, df_bugs
    except pd.errors.EmptyDataError:
        st.warning("🔄 Background sync in progress. Auto-refreshing soon...")
        st.stop()
    except Exception as e:
        st.error(f"Data Load Error: {e}"); st.stop()

@st.cache_data(ttl=600)
def fetch_html_calendar():
    calendar_times = {'NO_DATE': {}}
    headers = {'User-Agent': 'Mozilla/5.0'}
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
                    try: curr_date = datetime.strptime(f"{date_match.group(2)} {date_match.group(3)} 2026", "%B %d %Y").strftime("%Y-%m-%d")
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

def check_and_broadcast(df_bills, df_subscribers, demo_mode):
    if demo_mode: return
    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token: return
    client = WebClient(token=token)
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
        if not subscriber_list: return
        user_id = client.users_lookupByEmail(email=subscriber_list[0].strip())['user']['id']
        history = client.conversations_history(channel=client.conversations_open(users=[user_id])['channel']['id'], limit=100)
        history_text = "\n".join([m.get('text', '') for m in history['messages']]).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    except Exception: return
    
    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n_Latest changes detected:_\n"
    updates_found = False
    for i, row in df_bills.iterrows():
        if "LIS Connection Error" in str(row.get('Status')): continue
        b_num = str(row['Bill Number']).strip(); raw_status = str(row.get('Status', 'No Status')).strip(); clean_status = clean_status_text(raw_status)
        if b_num in history_text and clean_status in history_text: continue
        display_name = str(row.get('My Title', '-'))
        if display_name in ["-", "nan", ""]: official = str(row.get('Official Title', '')); display_name = (official[:60] + '..') if len(official) > 60 else official
        updates_found = True
        report += f"\n⚪ *{b_num}* | {display_name}\n> _{clean_status}_\n"
    
    if updates_found:
        for email in subscriber_list:
            try: uid = client.users_lookupByEmail(email=email.strip())['user']['id']; client.chat_postMessage(channel=uid, text=report)
            except: pass

def render_bill_card(row, show_youth_tag=False):
    official_title = str(row.get('Official Title', 'No Title'))
    my_title = str(row.get('My Title', '-')).strip()
    primary_title = f"⭐ {my_title}" if my_title and my_title not in ['nan', '-'] else official_title
    
    b_num_display = row['Bill Number']
    badge = "[H]" if str(b_num_display).upper().startswith("H") else ("[S]" if str(b_num_display).upper().startswith("S") else "")
    display_header = f"{b_num_display} {badge}"
    if show_youth_tag and row.get('Is_Youth', False): display_header = f"👶 {display_header}"
    
    st.markdown(f"**{display_header}**")
    lifecycle = str(row.get('Lifecycle', ''))
    if "Dead" in lifecycle or "Vetoed" in lifecycle: st.error(f"💀 {lifecycle}")
    elif "Passed" in lifecycle or "Signed" in lifecycle: st.success(f"🎉 {lifecycle}")
    elif "Out of Committee" in lifecycle: st.warning(f"📣 {lifecycle}")

    my_status = str(row.get('My Status', '')).strip()
    if my_status and my_status not in ['nan', '-']: st.info(f"🏷️ **Status:** {my_status}")
    st.caption(f"{primary_title}"); st.caption(f"_{clean_status_text(row.get('Status'))}_")
    st.markdown(f"[🔗 View on LIS](https://lis.virginia.gov/bill-details/20261/{row['Bill Number']})")
    st.divider()

def _render_single_bill_row(row):
    official_title = str(row.get('Official Title', 'No Title'))
    my_title = str(row.get('My Title', '-')).strip()
    
    if my_title and my_title not in ['nan', '-']:
        primary_title = f"⭐ {my_title}"
        sub_title_display = f"**📜 Official Title:** {official_title}"
    else:
        primary_title = official_title
        sub_title_display = ""

    my_status = str(row.get('My Status', '')).strip()
    label_text = f"{row['Bill Number']}"
    if my_status and my_status not in ['nan', '-']: label_text += f" - {my_status}"
    label_text += f" - {primary_title}"
    
    with st.expander(label_text):
        st.markdown(f"**🏛️ Current Location:** {row.get('Display_Committee', '-')}")
        clean_sub = get_clean_sub_name(row.get('Current_Sub', '-'))
        if clean_sub and clean_sub != '-': st.markdown(f"**↳ Subcommittee:** {clean_sub}")
        
        if my_title and my_title not in ['nan', '-']: st.markdown(f"**📌 Custom Title:** {my_title}")
        if sub_title_display: st.markdown(sub_title_display)
        
        st.markdown(f"**🔄 Status:** {clean_status_text(row.get('Status', '-'))}")
        hist_data = row.get('History_Data', [])
        if isinstance(hist_data, list) and hist_data:
            st.markdown("**📜 History:**")
            st.dataframe(pd.DataFrame(hist_data[::-1]), hide_index=True, use_container_width=True)
        else: st.caption(f"Date: {row.get('Date', '-')}")
        st.markdown(f"🔗 [View Official Bill on LIS](https://lis.virginia.gov/bill-details/20261/{row['Bill Number']})")


def render_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    df['Current_Sub'] = df.apply(lambda r: get_clean_sub_name(r.get('Current_Sub', '-')), axis=1)

    def clean_and_merge_names(name):
        name = str(name).strip()
        if name in ['-', 'nan', 'None', '', '0', 'Unassigned']: return "Unassigned"
        shared_committees = ["Agriculture", "Appropriations", "Commerce and Labor", "General Laws", "Privileges and Elections", "Rules", "Courts of Justice", "Transportation"]
        for shared in shared_committees:
            if name.lower().replace("house ", "").replace("senate ", "") == shared.lower(): return shared 
        return name

    df['Display_Comm_Group'] = df['Current_Committee'].fillna('-').apply(clean_and_merge_names)
    unique_committees = sorted(df['Display_Comm_Group'].unique())
    shared_lookup = ["Agriculture", "Appropriations", "Commerce and Labor", "General Laws", "Privileges and Elections", "Rules", "Courts of Justice", "Transportation"]

    for comm_name in unique_committees:
        st.markdown(f"##### 📂 {comm_name}")
        comm_df = df[df['Display_Comm_Group'] == comm_name]
        if comm_name == "Unassigned":
            for i, row in comm_df.iterrows(): _render_single_bill_row(row)
            continue
        
        if comm_name in shared_lookup:
            house_bills = comm_df[comm_df['Bill Number'].astype(str).str.upper().str.startswith('H')]
            senate_bills = comm_df[comm_df['Bill Number'].astype(str).str.upper().str.startswith('S')]
            for chamber_name, chamber_df in [("🏛️ House Bills", house_bills), ("🏛️ Senate Bills", senate_bills)]:
                if not chamber_df.empty:
                    st.markdown(f"**{chamber_name}**")
                    unique_subs = sorted([s for s in chamber_df['Current_Sub'].unique() if s != '-'])
                    if '-' in chamber_df['Current_Sub'].unique(): unique_subs.insert(0, '-')
                    for sub_name in unique_subs:
                        if sub_name != '-': st.markdown(f"**↳ {sub_name}**")
                        for i, row in chamber_df[chamber_df['Current_Sub'] == sub_name].iterrows(): _render_single_bill_row(row)
        else:
            unique_subs = sorted([s for s in comm_df['Current_Sub'].unique() if s != '-'])
            if '-' in comm_df['Current_Sub'].unique(): unique_subs.insert(0, '-')
            for sub_name in unique_subs:
                if sub_name != '-': st.markdown(f"**↳ {sub_name}**") 
                sub_df = comm_df[comm_df['Current_Sub'] == sub_name]
                for i, row in sub_df.iterrows(): _render_single_bill_row(row)

def render_passed_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    for state, title in [("✅ Signed & Enacted", "✅ Signed & Enacted"), ("✍️ Awaiting Signature", "✍️ Awaiting Signature"), ("✅ Passed (Resolution)", "📜 Resolution / Amendment (Passed)")]:
        subset = df[df['Lifecycle'] == state]
        if not subset.empty:
            st.markdown(f"##### {title}")
            for i, r in subset.iterrows(): _render_single_bill_row(r)

def render_failed_grouped_list_item(df):
    if df.empty: st.caption("No bills."); return
    for state, title in [("❌ Vetoed", "🏛️ Vetoed by Governor"), ("❌ Dead / Tabled", "❌ Dead / Tabled")]:
        subset = df[df['Lifecycle'] == state]
        if not subset.empty:
            st.markdown(f"##### {title}")
            for i, r in subset.iterrows(): _render_single_bill_row(r)

def render_simple_list_item(df):
    if df.empty: st.caption("No bills."); return
    def get_bucket(row):
        status_lower = str(row.get('Status', '')).lower()
        if "received from" in status_lower: return "1_Inbox"
        if any(x in status_lower for x in ["passed house", "passed senate", "communicated", "signed by speaker"]): return "3_Outbox"
        return "2_Floor"
    df['Bucket'] = df.apply(get_bucket, axis=1)
    bucket_map = {"1_Inbox": "📥 Received / Awaiting Referral", "2_Floor": "📜 On Floor", "3_Outbox": "🚀 Passed Chamber / In Transit"}
    for key in sorted(bucket_map.keys()):
        subset = df[df['Bucket'] == key]
        if not subset.empty:
            st.markdown(f"##### {bucket_map[key]}")
            for i, row in subset.iterrows(): _render_single_bill_row(row)

# --- MAIN APP START ---
st.title("🏛️ Virginia General Assembly Tracker")
est = pytz.timezone('US/Eastern')

# 1. LOAD DATABASES
current_time_block = int(time.time() // 300)
final_df, df_master, df_bugs = load_databases(current_time_block)
true_sync_time = get_last_sync_time()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Dashboard Mode")
    view_all_mode = st.toggle("🌐 View Entire Mastermind Database", value=False)
    if view_all_mode: st.caption("Showing all 3,600+ bills from the state database.")
    
    st.divider()
    # The Truth Clock
    st.markdown(f"**Last Database Update:** `{true_sync_time}`")
    
    # THE DIAGNOSTIC SENTRY
    if not final_df.empty:
        test_bills = final_df[final_df['My Title'].str.contains("TEST", case=False, na=False)]
        if not test_bills.empty:
            st.success(f"🧪 **LIVE DATA VERIFIED:** Found custom title: '{test_bills.iloc[0]['My Title']}'")
    
    st.divider()
    
    # 🚀 SURGERY 2: THE RESTORED GOD BUTTON (Immediate forced pull)
    if st.button("🚀 Force Manual Sync", type="primary", use_container_width=True):
        try:
            GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
            url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILENAME}/dispatches"
            headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
            data = {"ref": "main"}
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 204:
                progress_bar = st.progress(0, text="📡 Pinging State API...")
                for percent_complete in range(100):
                    time.sleep(0.6) 
                    progress_bar.progress(percent_complete + 1, text=f"⚙️ Ghost Worker syncing data... {60 - int((percent_complete + 1)*0.6)}s")
                
                st.cache_data.clear()
                st.rerun() 
            else:
                st.error(f"Failed to start worker: {response.status_code}")
        except Exception as e:
            st.error("GitHub Error: Missing token or connection issue.")
            
    st.caption("⚠️ Note: Lobbyists rely on the automatic 5-minute background refresh. This manual sync button is for Admins only.")

    st.divider()
    demo_mode = st.checkbox("🛠️ Enable Demo Mode", value=False)

# 2. RUN SCRAPER AND SLACK BOTS
try: subs_df = pd.read_csv(SUBS_URL)
except: subs_df = pd.DataFrame(columns=["Email"])
scraped_times, scrape_log = fetch_html_calendar() 
if not final_df.empty: check_and_broadcast(final_df, subs_df, demo_mode)

# --- 3. UI RENDERER ---
if view_all_mode:
    tab_data, tab_cal, tab_bugs = st.tabs(["🗃️ Master Spreadsheet", "📅 State Committee Calendar", "🪲 Bug Dashboard"])
    
    with tab_data:
        st.subheader("🌐 Global Mastermind Database")
        st.info("High-speed table view. Click any column header to sort, or hover over the table to use the search icon (magnifying glass) in the top right corner.")
        display_cols = ['Bill Number', 'Official Title', 'Status', 'Lifecycle', 'Auto_Folder', 'Display_Committee']
        st.dataframe(df_master[display_cols], use_container_width=True, hide_index=True, height=600)

else:
    tab_involved, tab_watching, tab_upcoming, tab_bugs = st.tabs(["🚀 Directly Involved", "👀 Watching", "📅 Your Hearings", "🪲 Bug Dashboard"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            st.subheader("🗂️ Browse by Topic")
            unique_folders = sorted(subset['Auto_Folder'].unique())
            has_youth = subset['Is_Youth'].any()
            if has_youth: unique_folders.insert(0, "👶 Youth & Children (All)")
            
            cols = st.columns(3)
            for i, folder in enumerate(unique_folders):
                with cols[i % 3]:
                    bills_in_folder = subset[subset['Is_Youth'] == True] if folder == "👶 Youth & Children (All)" else subset[subset['Auto_Folder'] == folder].sort_values(by='Is_Youth', ascending=False)
                    with st.expander(f"{folder} ({len(bills_in_folder)})"):
                        for _, row in bills_in_folder.iterrows(): render_bill_card(row, show_youth_tag=(folder != "👶 Youth & Children (All)"))
            
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            
            in_comm = subset[subset['Lifecycle'].isin(["📥 In Committee", "📥 Awaiting Referral"])]
            out_comm = subset[subset['Lifecycle'] == "📣 Out of Committee"]
            passed = subset[subset['Lifecycle'].isin(["✅ Signed & Enacted", "✍️ Awaiting Signature", "✅ Passed (Resolution)"])]
            failed = subset[subset['Lifecycle'].isin(["❌ Dead / Tabled", "❌ Vetoed"])]
            
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown("#### 📥 In Committee"); render_grouped_list_item(in_comm)
            with m2: st.markdown("#### 📣 Out of Committee"); render_simple_list_item(out_comm)
            with m3: st.markdown("#### 🎉 Passed"); render_passed_grouped_list_item(passed)
            with m4: st.markdown("#### ❌ Failed"); render_failed_grouped_list_item(failed)

# --- THE CALENDAR TAB ---
calendar_tab_target = tab_cal if view_all_mode else tab_upcoming
with calendar_tab_target:
    st.subheader("📅 Committee Agenda")
    today = datetime.now(est).date()
    cols = st.columns(7)
    
    def parse_time_rank(time_str):
        if not time_str or "TBA" in time_str: return 23.9 
        t_lower = time_str.lower()
        if "adjournment" in t_lower or "recess" in t_lower: return 12.5 
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
            if "pm" in t_lower and h != 12: h += 12
            if "am" in t_lower and h == 12: h = 0
            return h + (m / 60.0)
        return 23.9

    calendar_map = {}
    target_df = df_master if view_all_mode else final_df
    for _, row in target_df.iterrows():
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
                    d_obj = datetime.strptime(m_date_str, "%m/%d/%Y" if "/" in m_date_str else "%Y-%m-%d").date()
                    formatted_date = d_obj.strftime("%Y-%m-%d")
                    if formatted_date not in calendar_map: calendar_map[formatted_date] = {}
                    if clean_name not in calendar_map[formatted_date]: calendar_map[formatted_date][clean_name] = []
                    calendar_map[formatted_date][clean_name].append(row)
                except: pass

    for i in range(7):
        target_date = today + timedelta(days=i)
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        with cols[i]:
            st.markdown(f"**{target_date.strftime('%a %m/%d')}**")
            st.divider()
            
            comm_time_map = {} 
            if target_date_str in calendar_map:
                for comm_name in calendar_map[target_date_str].keys():
                    t_found, t_rank = "Time TBA", 23.9
                    if target_date_str in scraped_times:
                        docket_words = {w for w in set(comm_name.lower().replace("house","").replace("senate","").replace("committee","").split()) - {"of", "for", "and", "&", "-"} if len(w) > 3}
                        if docket_words:
                            for s_key, s_time in scraped_times[target_date_str].items():
                                s_key_lower = s_key.lower()
                                if ("house" in comm_name.lower() and "senate" in s_key_lower) or ("senate" in comm_name.lower() and "house" in s_key_lower): continue
                                if any(w in s_key_lower for w in docket_words):
                                    t_found, t_rank = s_time, parse_time_rank(s_time)
                                    break
                    comm_time_map[comm_name] = {"display": t_found, "rank": t_rank}

                sorted_comms = sorted(calendar_map[target_date_str].items(), key=lambda x: comm_time_map.get(x[0], {}).get('rank', 23.9))
                for comm_name, bills in sorted_comms:
                    st.markdown(f"**{comm_name}**\n\n⏰ {comm_time_map.get(comm_name, {}).get('display', 'Time TBA')}")
                    for row in bills: _render_single_bill_row(row)
                    st.divider()

            if i == 0: 
                completed_map = {}
                for _, row in target_df.iterrows():
                    is_dup = False
                    if target_date_str in calendar_map:
                        for c_list in calendar_map[target_date_str].values():
                            if row['Bill Number'] in [r['Bill Number'] for r in c_list]: is_dup = True
                    if is_dup: continue

                    happened_today = False
                    if isinstance(row.get('History_Data', []), list):
                        for h in row.get('History_Data', []):
                            try:
                                h_date_str = str(h.get('Date', ''))
                                if datetime.strptime(h_date_str, "%m/%d/%Y" if "/" in h_date_str else "%Y-%m-%d").date() == target_date: happened_today = True
                            except: pass
                    
                    if not happened_today:
                        try:
                            last_date = str(row.get('Date', ''))
                            if datetime.strptime(last_date, "%m/%d/%Y" if "/" in last_date else "%Y-%m-%d").date() == target_date: happened_today = True
                        except: pass

                    if not happened_today and (target_date.strftime("%-m/%-d/%Y") in str(row.get('Status', '')) or target_date.strftime("%m/%d/%Y") in str(row.get('Status', ''))): happened_today = True

                    if happened_today:
                        status_lower = str(row.get('Status', '')).lower()
                        if any(x in status_lower for x in ["passed", "report", "agreed", "engross", "read", "vote", "tabled", "failed", "defeat", "stricken", "indefinitely", "left in", "incorporated", "no action", "continued", "withdrawn", "recommitted", "rereferred", "carried over", "approved"]) or bool(re.search(r'\d{1,3}-y', status_lower)):
                            if not any(x in status_lower for x in ["fiscal impact", "statement from", "note filed", "assigned", "referred", "docketed"]):
                                group_key = row.get('Display_Committee', 'Other Actions')
                                if group_key == "On Floor / Reported" or "Chamber" in group_key: group_key = "House Floor / General Orders" if row['Bill Number'].startswith('H') else "Senate Floor / General Orders"
                                if group_key not in completed_map: completed_map[group_key] = []
                                completed_map[group_key].append(row)

                if completed_map:
                    st.success("✅ **Completed Today**")
                    for comm_key, bills in sorted(completed_map.items(), key=lambda x: comm_time_map.get(x[0], {}).get('rank', 12.0)):
                        st.markdown(f"**{comm_key}**")
                        for row in bills:
                            my_status, vote_str = str(row.get('My Status', '')).strip(), extract_vote_info(row.get('Status', ''))
                            label_text = f"{row['Bill Number']} **PASSED {vote_str}**" if vote_str else (f"{row['Bill Number']} - {my_status}" if my_status not in ['-', 'nan'] else row['Bill Number'])
                            with st.expander(label_text):
                                st.markdown(f"**🔄 Outcome:** {clean_status_text(row.get('Status', '-'))}\n\n📌 {row.get('My Title', '-')}")
                                st.markdown(f"🔗 [View on LIS](https://lis.virginia.gov/bill-details/20261/{row['Bill Number']})")
                        st.divider()

            if not (target_date_str in calendar_map) and not (i == 0 and 'completed_map' in locals() and len(completed_map) > 0):
                 st.caption("-") if i != 0 else st.info("No hearings or updates yet today.")

# --- TAB 4: BUG TRACKER ---
with tab_bugs:
    st.subheader("🪲 System Diagnostics & Bug Dashboard")
    st.info("Tracking active breaks in the data pipeline. Review open bugs and repair them in the backend logic.")
    
    if df_bugs.empty:
        st.success("✅ Master log is empty. No bugs found!")
    else:
        open_bugs = df_bugs[df_bugs['Status'] == "🚨 Open"]
        if open_bugs.empty:
            st.success("✅ 0 Open Bugs. System is completely healthy.")
        else:
            vocab = open_bugs[open_bugs['Bug_Type'] == "🚨 Unrecognized Status Phrase"]
            with st.expander(f"🚨 Unrecognized Status Phrase ({len(vocab)})"):
                st.write("**How to fix:** Open `backend_worker.py` and add the new phrase to the `determine_lifecycle` dictionary.")
                if not vocab.empty: st.dataframe(vocab[['Bill_Number', 'Details', 'Date_Found']], hide_index=True)
            
            routing = open_bugs[open_bugs['Bug_Type'] == "🧭 Unmapped Committee Name"]
            with st.expander(f"🧭 Unmapped Committee Name ({len(routing)})"):
                st.write("**How to fix:** Open `backend_worker.py` and add the exact spelling the state used to the `COMMITTEE_MAP`.")
                if not routing.empty: st.dataframe(routing[['Bill_Number', 'Details', 'Date_Found']], hide_index=True)

            sorting = open_bugs[open_bugs['Bug_Type'] == "🗂️ Missing Topic Keyword"]
            with st.expander(f"🗂️ Missing Topic Keyword ({len(sorting)})"):
                st.write("**How to fix:** Read the bill's title and add one or two relevant words from it into `TOPIC_KEYWORDS`.")
                if not sorting.empty: st.dataframe(sorting[['Bill_Number', 'Details', 'Date_Found']], hide_index=True)

            sync = open_bugs[open_bugs['Bug_Type'] == "🔌 Background Sync Failure"]
            with st.expander(f"🔌 Background Sync Failures ({len(sync)})"):
                st.write("**How to fix:** Log into GitHub and check for server errors or expired security tokens.")
                if not sync.empty: st.dataframe(sync[['Details', 'Date_Found']], hide_index=True)
