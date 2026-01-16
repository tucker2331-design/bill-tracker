import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, timedelta
import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

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
    # Strip names
    name = re.sub(r'\b[A-Z][a-z]+, [A-Z]\. ?[A-Z]?\.?.*$', '', name) 
    name = re.sub(r'\b(Simon|Rasoul|Willett|Helmer|Lucas|Surovell|Locke|Deeds|Favola|Marsden|Ebbin|McPike|Hayes|Carroll Foy|Subcommittee #\d+)\b.*', '', name, flags=re.IGNORECASE)
    return name.strip().title()

def clean_status_text(text):
    if not text: return ""
    text = str(text)
    return text.replace("HED", "House Education").replace("sub:", "Subcommittee:")

# --- DATA FETCHING (DOCKET + HISTORY) ---
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

    # 1. BILLS
    df_bills = load_csv(LIS_BILLS_CSV)
    if not df_bills.empty:
        col = 'bill_number' if 'bill_number' in df_bills.columns else 'bill_id'
        if col in df_bills.columns: df_bills['bill_clean'] = df_bills[col].astype(str).apply(clean_bill_id)
    data['bills'] = df_bills

    # 2. HISTORY
    df_hist = load_csv(LIS_HISTORY_CSV)
    if not df_hist.empty:
        col = 'bill_number' if 'bill_number' in df_hist.columns else 'bill_id'
        if col in df_hist.columns: df_hist['bill_clean'] = df_hist[col].astype(str).apply(clean_bill_id)
    data['history'] = df_hist

    # 3. DOCKET (Calendar)
    df_docket = load_csv(LIS_DOCKET_CSV)
    if not df_docket.empty:
        # MAP WEIRD COLUMNS
        # LIS DOCKET.CSV cols are often: 'com_des', 'meet_date', 'meet_time', 'bill_no'
        
        # 1. Find Bill Column
        bill_col = next((c for c in df_docket.columns if c in ['bill_no', 'bill_number', 'bill_id']), None)
        if bill_col: df_docket['bill_clean'] = df_docket[bill_col].astype(str).apply(clean_bill_id)
        
        # 2. Rename for consistency
        rename_map = {}
        for c in df_docket.columns:
            if 'com' in c and 'des' in c: rename_map[c] = 'committee_name'
            if 'date' in c and 'meet' in c: rename_map[c] = 'meeting_date'
            if 'time' in c and 'meet' in c: rename_map[c] = 'meeting_time'
        df_docket.rename(columns=rename_map, inplace=True)
        
    data['docket'] = df_docket

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
                        if match: found = match.group(1).strip().title(); curr_comm = found if len(found) > 3 else curr_comm
                    if "sub:" in desc_lower:
                        try: curr_sub = desc_lower.split("sub:")[1].strip().title()
                        except: pass
        
        if curr_comm == "-":
            potential_cols = ['last_house_committee', 'last_senate_committee', 'house_committee', 'senate_committee']
            if item:
                for col in potential_cols:
                    val = item.get(col)
                    if pd.notna(val) and str(val).strip() not in ['nan', '', '-', '0']: curr_comm = str(val).strip(); break
        
        curr_comm = clean_committee_name(curr_comm)
        lifecycle = determine_lifecycle(str(status), str(curr_comm))
        display_comm = curr_comm
        if lifecycle == "📣 Out of Committee" or lifecycle == "✅ Signed & Enacted":
             if "engross" in str(status).lower(): display_comm = "🏛️ Engrossed (Passed Chamber)"
             elif "read" in str(status).lower(): display_comm = "📜 On Floor (Read/Reported)"
             elif "passed" in str(status).lower(): display_comm = "🎉 Passed Chamber"
             else: display_comm = "On Floor / Reported"

        # --- DOCKET MATCHING (FIXED COLUMNS) ---
        upcoming_meetings = []
        raw_docket = docket_lookup.get(bill_num, [])
        for d in raw_docket:
            # Flexible Key Search
            d_date = d.get('meeting_date')
            d_time = d.get('meeting_time', 'TBA')
            d_comm = d.get('committee_name', 'Unknown')
            
            if d_date:
                # Format Date
                try:
                    # LIS usually uses MM/DD/YYYY
                    if "/" in str(d_date): 
                        dt_obj = datetime.strptime(str(d_date), "%m/%d/%Y")
                        fmt_date = dt_obj.strftime("%Y-%m-%d")
                    else:
                        fmt_date = str(d_date)
                except: fmt_date = str(d_date)

                upcoming_meetings.append({
                    "Date": fmt_date,
                    "Time": str(d_time),
                    "Committee": clean_committee_name(str(d_comm))
                })

        results.append({
            "Bill Number": bill_num, "Official Title": title, "Status": str(status), "Date": date_val, 
            "Lifecycle": lifecycle, "Auto_Folder": get_smart_subject(title), "History_Data": history_data[::-1], 
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
        st.toast(f"📢 Sending updates to {len(subscriber_list)} people...")
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
        if name in ['-', 'nan', 'None', '', '0']: return "Unassigned"
        if name == "House -": return "House - Unassigned"
        if name == "Senate -": return "Senate - Unassigned"
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

# 2. FETCH DATA
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()

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
            passed = subset[subset['Lifecycle'].isin(["✅ Signed & Enacted", "✍️ Awaiting Signature"])]
            failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.markdown("#### 📥 In Committee"); render_grouped_list_item(in_comm)
            with m2: st.markdown("#### 📣 Out of Committee"); render_simple_list_item(out_comm)
            with m3: st.markdown("#### 🎉 Passed"); render_simple_list_item(passed)
            with m4: st.markdown("#### ❌ Failed"); render_simple_list_item(failed)

    # --- TAB 3: CALENDAR (DOCKET FILE) ---
    with tab_upcoming:
        st.subheader("📅 Your Confirmed Agenda")
        today = datetime.now(est).date()
        cols = st.columns(7)
        
        # Build Calendar Map from the 'Upcoming_Meetings' column in final_df
        calendar_map = {}
        for _, row in final_df.iterrows():
            meetings = row.get('Upcoming_Meetings', [])
            if isinstance(meetings, list):
                for m in meetings:
                    m_date_str = str(m['Date']).split(" ")[0]
                    try:
                        if "/" in m_date_str: d_obj = datetime.strptime(m_date_str, "%m/%d/%Y").date()
                        else: d_obj = datetime.strptime(m_date_str, "%Y-%m-%d").date()
                        formatted_date = d_obj.strftime("%Y-%m-%d")
                        
                        if formatted_date not in calendar_map: calendar_map[formatted_date] = []
                        # Pass full row info to the calendar event
                        calendar_map[formatted_date].append({
                            'Bill': row['Bill Number'],
                            'My Title': row.get('My Title', '-'),
                            'Official Title': row.get('Official Title', '-'),
                            'My Status': row.get('My Status', '-'),
                            'Status': row.get('Status', '-'),
                            'Time': m['Time'],
                            'Committee': m['Committee'],
                            'Current_Committee': row.get('Current_Committee', '-'),
                            'Current_Sub': row.get('Current_Sub', '-'),
                            'History_Data': row.get('History_Data', [])
                        })
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
                    events = calendar_map[target_date_str]
                    for e in events:
                        st.markdown(f"**{e['Committee']}**")
                        st.caption(f"⏰ {e['Time']}")
                        
                        # RENDER FULL CARD HERE
                        label_text = f"✅ {e['Bill']}"
                        if e['My Status'] != '-': label_text += f" - {e['My Status']}"
                        
                        with st.expander(label_text):
                            st.markdown(f"**📌 Designated Title:** {e['My Title']}")
                            st.markdown(f"**📜 Official Title:** {e['Official Title']}")
                            st.markdown(f"**🔄 Status:** {clean_status_text(e['Status'])}")
                            
                            hist_data = e.get('History_Data', [])
                            if isinstance(hist_data, list) and hist_data:
                                st.markdown("**📜 History:**")
                                st.dataframe(pd.DataFrame(hist_data), hide_index=True, use_container_width=True)
                            
                            lis_link = f"https://lis.virginia.gov/bill-details/20261/{e['Bill']}"
                            st.markdown(f"🔗 [View Official Bill on LIS]({lis_link})")
                        st.divider()

                # SECTION 2: COMPLETED ACTIONS (FROM HISTORY - RESTORED!)
                if i == 0:
                    events_found = False
                    for _, row in final_df.iterrows():
                        last_date = str(row.get('Date', ''))
                        is_today = False
                        try:
                            # Handle M/D/Y vs Y-M-D
                            if "/" in last_date: lis_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
                            else: lis_dt = datetime.strptime(last_date, "%Y-%m-%d").date()
                            if lis_dt == target_date: is_today = True
                        except: pass
                        
                        if is_today:
                            # Filter out admin actions (referred, printed)
                            lis_status = str(row.get('Status', '')).lower()
                            is_outcome = any(x in lis_status for x in ["reported", "passed", "defeat", "stricken", "agreed", "read", "engross", "vote"])
                            
                            if is_outcome:
                                if not events_found: 
                                    st.caption("🏁 **Completed Today**")
                                    events_found = True
                                    
                                _render_single_bill_row(row)

                if not (target_date_str in calendar_map) and (i != 0 or not events_found):
                    st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("System Status:")
        if 'docket' in lis_data and not lis_data['docket'].empty:
             st.write(f"**Docket File:** 🟢 Loaded ({len(lis_data['docket'])} rows)")
             # Debug columns to fix mapping
             st.write(f"**Found Columns:** {list(lis_data['docket'].columns)}")
        else:
             st.write(f"**Docket File:** 🔴 Not Found")
        
        if 'history' in lis_data and not lis_data['history'].empty:
             st.write(f"**History File:** 🟢 Loaded ({len(lis_data['history'])} rows)")
        else:
             st.write(f"**History File:** 🔴 Not loaded")
