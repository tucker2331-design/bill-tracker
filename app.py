import streamlit as st
import pandas as pd
import requests
import time
import re 
from datetime import datetime, timedelta
import pytz # For EST Timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
BILLS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
SUBS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Subscribers"

# --- VIRGINIA LIS DATA FEEDS ---
LIS_BASE_URL = "https://lis.blob.core.windows.net/lisfiles/20261/"
LIS_BILLS_CSV = LIS_BASE_URL + "BILLS.CSV"      
LIS_SUBDOCKET_CSV = LIS_BASE_URL + "SUBDOCKET.CSV"  # Subcommittees
LIS_DOCKET_CSV = LIS_BASE_URL + "DOCKET.CSV"        # Main Standing Committees
LIS_CALENDAR_CSV = LIS_BASE_URL + "CALENDAR.CSV"    # Floor Sessions / Votes

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- EXPANDED SMART CATEGORIZATION ---
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

def determine_lifecycle(status_text):
    status = str(status_text).lower()
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]):
        return "✅ Signed & Enacted"
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]):
        return "❌ Dead / Tabled"
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]):
        return "✍️ Awaiting Signature"
    return "🚀 Active"

def get_smart_subject(title):
    title_lower = str(title).lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "📂 Unassigned / General"

# --- DATA FETCHING (DIRECT FROM LIS) ---
@st.cache_data(ttl=300) 
def fetch_lis_data():
    data = {}
    
    # 1. Fetch Bills
    try:
        try: df = pd.read_csv(LIS_BILLS_CSV, encoding='ISO-8859-1')
        except: df = pd.read_csv(LIS_BILLS_CSV.replace(".CSV", ".csv"), encoding='ISO-8859-1')
        
        # FIX: Normalize columns heavily
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
        
        if 'bill_id' in df.columns:
            df['bill_clean'] = df['bill_id'].astype(str).str.upper().str.replace(" ", "").str.strip()
            data['bills'] = df
        else: data['bills'] = pd.DataFrame() 
    except: data['bills'] = pd.DataFrame()

    # 2. Fetch Calendars
    calendar_dfs = []
    # Note: We tag them here so we know if it came from the Subcommittee file
    for url, type_label in [(LIS_SUBDOCKET_CSV, "Subcommittee"), (LIS_DOCKET_CSV, "Committee"), (LIS_CALENDAR_CSV, "Floor")]:
        try:
            try: df = pd.read_csv(url, encoding='ISO-8859-1')
            except: df = pd.read_csv(url.replace(".CSV", ".csv"), encoding='ISO-8859-1')
            
            # FIX: Normalize columns heavily here too
            df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
            
            # Dynamically find the bill number column
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

def get_bill_data_batch(bill_numbers, lis_df):
    results = []
    # FIX: Remove spaces from input for matching
    clean_bills = list(set([str(b).strip().upper().replace(" ", "") for b in bill_numbers if str(b).strip() != 'nan']))
    
    if lis_df.empty:
        for b in clean_bills:
             results.append({"Bill Number": b, "Status": "LIS Connection Error", "Lifecycle": "🚀 Active", "Official Title": "Error"})
        return pd.DataFrame(results)

    lis_lookup = lis_df.set_index('bill_clean').to_dict('index')
    for bill_num in clean_bills:
        item = lis_lookup.get(bill_num)
        if item:
            status = item.get('last_house_action', '')
            if pd.isna(status) or str(status).strip() == '': status = item.get('last_senate_action', 'Introduced')
            title = item.get('bill_description', 'No Title')
            
            date_val = str(item.get('last_house_action_date', ''))
            if not date_val or date_val == 'nan':
                date_val = str(item.get('last_senate_action_date', ''))

            # History Data
            history_data = []
            h_act = item.get('last_house_action')
            if pd.notna(h_act) and str(h_act).lower() != 'nan':
                 history_data.append({"Date": item.get('last_house_action_date'), "Action": f"[House] {h_act}"})
            s_act = item.get('last_senate_action')
            if pd.notna(s_act) and str(s_act).lower() != 'nan':
                 history_data.append({"Date": item.get('last_senate_action_date'), "Action": f"[Senate] {s_act}"})

            # --- ROBUST COMMITTEE EXTRACTION ---
            curr_comm = "-"
            
            # 1. Try explicit columns first
            c1 = item.get('last_house_committee')
            c2 = item.get('last_senate_committee')
            if pd.notna(c1) and str(c1).strip() not in ['nan', '']: curr_comm = c1
            elif pd.notna(c2) and str(c2).strip() not in ['nan', '']: curr_comm = c2
            
            # 2. Status Text Regex (Better for Resolutions like "Referred to Rules")
            status_lower = str(status).lower()
            if curr_comm == "-":
                # Matches: "referred to committee on X", "referred to X"
                comm_match = re.search(r'referred to (?:committee on|the committee on)?\s?([a-z\s&]+)', status_lower)
                if comm_match:
                    curr_comm = comm_match.group(1).title().strip()
            
            # 3. Sub-committee extraction from Status Text
            curr_sub = "-"
            if "sub:" in status_lower:
                try:
                    parts = status_lower.split("sub:")
                    if curr_comm == "-": curr_comm = parts[0].replace("assigned", "").strip().title()
                    curr_sub = parts[1].strip().title()
                except: pass

            results.append({
                "Bill Number": bill_num,
                "Official Title": title,
                "Status": str(status),
                "Date": date_val, 
                "Lifecycle": determine_lifecycle(str(status)),
                "Auto_Folder": get_smart_subject(title),
                "History_Data": history_data,
                "Current_Committee": str(curr_comm).strip(),
                "Current_Sub": str(curr_sub).strip()
            })
        else:
            results.append({
                "Bill Number": bill_num, "Status": "Not Found on LIS", "Lifecycle": "🚀 Active", "Official Title": "Unknown"
            })
    return pd.DataFrame(results)

# --- ALERTS ---

def check_and_broadcast(df_bills, df_subscribers, demo_mode):
    st.sidebar.header("🤖 Slack Bot Status")
    if demo_mode:
        st.sidebar.warning("🛠️ Demo Mode Active")
        return

    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token: 
        st.sidebar.error("❌ Disconnected (Token Missing)")
        return
    client = WebClient(token=token)
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
        if not subscriber_list: 
            st.sidebar.warning("⚠️ No Subscribers Found")
            return
        user_id = client.users_lookupByEmail(email=subscriber_list[0].strip())['user']['id']
        history = client.conversations_history(channel=client.conversations_open(users=[user_id])['channel']['id'], limit=100)
        history_text = "\n".join([m.get('text', '') for m in history['messages']])
        st.sidebar.success(f"✅ Connected to Slack")
    except Exception as e:
        st.sidebar.error(f"❌ Slack Error: {e}")
        return

    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n_Latest changes detected:_\n"
    updates_found = False
    
    for i, row in df_bills.iterrows():
        if "LIS Connection Error" in str(row.get('Status')): continue
        display_date = row.get('Date', '')
        if not display_date or display_date == 'nan': display_date = datetime.now().strftime('%Y-%m-%d')
        check_str = f"*{row['Bill Number']}* ({display_date}): {row.get('Status')}"
        if check_str in history_text: continue
        updates_found = True
        report += f"\n⚪ {check_str}"

    if updates_found:
        st.toast(f"📢 Sending updates to {len(subscriber_list)} people...")
        for email in subscriber_list:
            try:
                uid = client.users_lookupByEmail(email=email.strip())['user']['id']
                client.chat_postMessage(channel=uid, text=report)
            except: pass
        st.toast("✅ Sent!")
        st.sidebar.info("🚀 New Update Sent!")
    else:
        st.sidebar.info("💤 No new updates needed.")

# --- UI COMPONENTS ---

def render_bill_card(row):
    if row.get('Official Title') not in ["Unknown", "Error", "Not Found", None]:
        display_title = row['Official Title']
    else:
        display_title = row.get('My Title', 'No Title Provided')
    st.markdown(f"**{row['Bill Number']}**")
    st.caption(f"{display_title}")
    st.caption(f"_{row.get('Status')}_")
    st.divider()

def render_master_list_item(df):
    if df.empty:
        st.caption("No bills.")
        return
    for i, row in df.iterrows():
        header_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', '')
        with st.expander(f"{row['Bill Number']} - {header_title}"):
            st.markdown(f"**🏛️ Current Committee:** {row.get('Current_Committee', '-')}")
            if row.get('Current_Sub') and row.get('Current_Sub') != '-':
                st.markdown(f"**↳ Subcommittee:** {row.get('Current_Sub')}")
                
            st.markdown(f"**📌 Designated Title:** {row.get('My Title', '-')}")
            st.markdown(f"**📜 Official Title:** {row.get('Official Title', '-')}")
            st.markdown(f"**🔄 Status:** {row.get('Status', '-')}")
            
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
    
    df_w = pd.DataFrame()
    if 'Bills Watching' in raw_df.columns:
        df_w = raw_df[['Bills Watching', 'Title (Watching)']].copy()
        df_w.columns = ['Bill Number', 'My Title']
        df_w['Type'] = 'Watching'
    df_i = pd.DataFrame()
    w_col = next((c for c in raw_df.columns if "Working On" in c), None)
    if w_col:
        df_i = raw_df[[w_col]].copy()
        df_i.columns = ['Bill Number']
        df_i['My Title'] = "-"
        df_i['Type'] = 'Involved'

    sheet_df = pd.concat([df_w, df_i], ignore_index=True).dropna(subset=['Bill Number'])
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper().str.replace(" ", "")
    sheet_df = sheet_df[sheet_df['Bill Number'] != 'NAN']
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# 2. FETCH LIS DATA
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    # Match User Bills to LIS Data
    if demo_mode:
        import random
        mock_results = []
        for b in bills_to_track:
            mock_results.append({
                "Bill Number": b, "Official Title": "[DEMO] Bill Title", "Status": "Referred to Commerce",
                "Lifecycle": "🚀 Active", "Auto_Folder": "💰 Economy & Business",
                "My Title": "Demo Title", "Date": "2026-01-14",
                "History_Data": [], "Current_Committee": "Commerce", "Current_Sub": "-"
            })
        api_df = pd.DataFrame(mock_results)
    else:
        api_df = get_bill_data_batch(bills_to_track, lis_data['bills'])

    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    def assign_folder(row):
        title_to_check = row.get('Official Title', '')
        if str(title_to_check) in ["Unknown", "Error", "Not Found", "nan", "None", ""]:
            title_to_check = row.get('My Title', '')
        return get_smart_subject(str(title_to_check))

    if 'Auto_Folder' not in final_df.columns or final_df['Auto_Folder'].isnull().any():
         final_df['Auto_Folder'] = final_df.apply(assign_folder, axis=1)

    check_and_broadcast(final_df, subs_df, demo_mode)

    # 3. RENDER TABS
    tab_involved, tab_watching, tab_upcoming = st.tabs(["🚀 Directly Involved", "👀 Watching", "📅 Upcoming Hearings"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            st.subheader("🗂️ Browse by Topic")
            unique_folders = sorted(subset['Auto_Folder'].unique())
            if len(unique_folders) == 0:
                st.info("No bills found.")
            else:
                cols = st.columns(3)
                for i, folder in enumerate(unique_folders):
                    with cols[i % 3]:
                        bills_in_folder = subset[subset['Auto_Folder'] == folder]
                        with st.expander(f"{folder} ({len(bills_in_folder)})"):
                            for _, row in bills_in_folder.iterrows():
                                render_bill_card(row)
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            active = subset[subset['Lifecycle'] == "🚀 Active"]
            awaiting = subset[subset['Lifecycle'] == "✍️ Awaiting Signature"]
            signed = subset[subset['Lifecycle'] == "✅ Signed & Enacted"]
            dead = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown("#### 🚀 Active")
                render_master_list_item(active)
            with m2:
                st.markdown("#### 🎉 Passed")
                render_master_list_item(pd.concat([awaiting, signed]))
            with m3:
                st.markdown("#### ❌ Failed")
                render_master_list_item(dead)

    # --- TAB 3: UPCOMING (INVERTED LOOP & TEXT SCRAPER) ---
    with tab_upcoming:
        st.subheader("📅 Your Weekly Calendar")
        full_schedule = lis_data.get('schedule', pd.DataFrame())

        if not full_schedule.empty:
            date_col = next((c for c in full_schedule.columns if "date" in c), None)
            if date_col:
                full_schedule['dt'] = pd.to_datetime(full_schedule[date_col], errors='coerce')
            else:
                full_schedule['dt'] = pd.NaT

        # --- THE BRAIN: Maps from Master List ---
        bill_to_comm_map = final_df.set_index('Bill Number')['Current_Committee'].to_dict()
        bill_to_sub_map = final_df.set_index('Bill Number')['Current_Sub'].to_dict()
        bill_to_status_map = final_df.set_index('Bill Number')['Status'].to_dict()

        today = datetime.now().date()
        cols = st.columns(7)
        my_bills = [b.upper() for b in bills_to_track]
        
        for i in range(7):
            target_date = today + timedelta(days=i)
            display_date_str = target_date.strftime("%a %m/%d")
            
            with cols[i]:
                st.markdown(f"**{display_date_str}**")
                st.divider()
                
                # Filter schedule for this specific date
                if not full_schedule.empty and 'dt' in full_schedule.columns:
                    todays_schedule = full_schedule[full_schedule['dt'].dt.date == target_date]
                    
                    if not todays_schedule.empty:
                        # --- KEY CHANGE: Iterate through MY BILLS, not the schedule ---
                        # This ensures even if the bill isn't explicitly listed, we find the committee meeting
                        
                        bills_found_today = False
                        
                        for bill in my_bills:
                            # 1. Get Bill's "Brain" Data
                            master_comm = bill_to_comm_map.get(bill, '').lower()
                            master_status = bill_to_status_map.get(bill, '')
                            master_sub = bill_to_sub_map.get(bill, '')

                            # 2. Search Logic
                            # Match A: Bill is explicitly in the schedule row
                            match_explicit = todays_schedule[todays_schedule['bill_clean'] == bill]
                            
                            # Match B: Committee Name matches (Implicit Match)
                            # We check if 'master_comm' (e.g. "Privileges and Elections") appears in the schedule row string
                            match_implicit = pd.DataFrame()
                            if master_comm and master_comm != '-':
                                # We scan all columns for the committee name
                                match_implicit = todays_schedule[
                                    todays_schedule.apply(lambda r: master_comm in str(r.values).lower(), axis=1)
                                ]
                            
                            # Combine matches
                            final_matches = pd.concat([match_explicit, match_implicit]).drop_duplicates()
                            
                            if not final_matches.empty:
                                bills_found_today = True
                                # Pick the first relevant meeting found
                                row = final_matches.iloc[0]
                                
                                st.error(f"**{bill}**")
                                
                                # Header (Prefer Master List Committee)
                                header = master_comm.title() if master_comm and master_comm != '-' else "Committee"
                                st.write(f"🏛️ **{header}**")
                                
                                if master_sub and master_sub != '-':
                                    st.caption(f"↳ {master_sub}")

                                if master_status:
                                    st.caption(f"ℹ️ {master_status}")

                                # --- 3. TIME SCRAPER (KEYWORD UPGRADE) ---
                                row_text = " ".join([str(val) for val in row.values])
                                
                                # Look for digits (8:00) OR keywords (Upon, After, Recess)
                                time_keywords = r'(?:upon|after|before)\s+(?:adjourn|recess|conven)|(?:\d+\s+minutes?\s+after)|(\d{1,2}:\d{2}\s?(?:[ap]\.?m\.?|noon))'
                                t_match = re.search(time_keywords, row_text, re.IGNORECASE)
                                
                                if t_match:
                                    st.caption(f"⏰ {t_match.group(0)}") # Grab the whole match (e.g. "Upon Recess")
                                else:
                                    st.caption("⏰ TBD")
                                
                                st.divider()

                        if not bills_found_today:
                            st.caption("-")
                    else:
                        st.caption("-")
                else:
                    st.caption("-")
