import streamlit as st
import pandas as pd
import requests
import time
import re
from datetime import datetime, timedelta
import pytz
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from bs4 import BeautifulSoup # <--- REQUIRED: pip install beautifulsoup4

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

def normalize_text(text):
    """Normalize text for better matching (remove punctuation, lower case, standardize 'and')"""
    if pd.isna(text): return ""
    text = str(text).lower()
    text = text.replace('&', 'and').replace('.', '').replace(',', '')
    return " ".join(text.split())

# --- NEW: DUAL-MODE SCRAPER ---
@st.cache_data(ttl=600)
def fetch_schedule_from_web():
    schedule_map = {}
    debug_log = [] 
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    targets = [
        ("https://apps.senate.virginia.gov/Senator/ComMeetings.php", "Senate"),
        ("https://virginiageneralassembly.gov/house/schedule/schedule.php", "House")
    ]

    for url, label in targets:
        try:
            debug_log.append(f"🔄 {label}: {url}")
            response = requests.get(url, headers=headers, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Senate & House text stream extraction
            all_text = soup.get_text("\n", strip=True)
            lines = all_text.splitlines()
            
            debug_log.append(f"   📄 Extracted {len(lines)} lines.")
            current_date_str = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if len(line) < 3: continue

                # A. DATE TRIGGER
                if "2026" in line:
                    try:
                        clean_line = line.replace("1st", "1").replace("2nd", "2").replace("3rd", "3").replace("th", "")
                        match = re.search(r'([A-Za-z]+, )?([A-Za-z]+ \d{1,2}, \d{4})', clean_line)
                        if match:
                            dt_str = match.group(0)
                            try: dt = datetime.strptime(dt_str, "%A, %B %d, %Y")
                            except: dt = datetime.strptime(dt_str, "%B %d, %Y")
                            current_date_str = dt.strftime("%Y-%m-%d")
                            continue
                    except: pass
                
                if not current_date_str: continue

                # B. TIME TRIGGER
                time_pattern = r'(\d{1,2}:\d{2}\s*?[aApP]\.?[mM]\.?|Noon|Upon\s+.*?|1\/2\s+hr|\d+\s+min)'
                time_match = re.search(time_pattern, line, re.IGNORECASE)
                
                if time_match:
                    time_val = time_match.group(0)
                    
                    # C. FIND COMMITTEE NAME (Check Prev Line then Current Line)
                    candidate_name = ""
                    if i > 0:
                        prev = lines[i-1].strip()
                        if len(prev) > 4 and "Agenda" not in prev and "View" not in prev:
                            candidate_name = prev
                    
                    if len(candidate_name) < 4:
                        candidate_name = line.replace(time_val, "").strip(" -:")

                    if "New Meeting" in candidate_name: continue
                    
                    clean_name = normalize_text(candidate_name)
                    clean_name = clean_name.replace("senate", "").replace("house", "").replace("committee", "").strip()
                    
                    if len(clean_name) > 3:
                        key = (current_date_str, clean_name)
                        if key not in schedule_map:
                            schedule_map[key] = time_val

        except Exception as e:
            debug_log.append(f"❌ {label} Error: {str(e)}")

    st.session_state['debug_data'] = {
        "map_keys": list(schedule_map.keys()),
        "log": debug_log
    }
    return schedule_map

# --- DATA FETCHING (DIRECT FROM LIS) ---
@st.cache_data(ttl=300) 
def fetch_lis_data():
    data = {}
    try:
        try: df = pd.read_csv(LIS_BILLS_CSV, encoding='ISO-8859-1')
        except: df = pd.read_csv(LIS_BILLS_CSV.replace(".CSV", ".csv"), encoding='ISO-8859-1')
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
        if 'bill_id' in df.columns:
            df['bill_clean'] = df['bill_id'].astype(str).str.upper().str.replace(" ", "").str.strip()
            data['bills'] = df
        else: data['bills'] = pd.DataFrame() 
    except: data['bills'] = pd.DataFrame()
    return data

def get_bill_data_batch(bill_numbers, lis_df):
    results = []
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
            c1 = item.get('last_house_committee')
            c2 = item.get('last_senate_committee')
            if pd.notna(c1) and str(c1).strip() not in ['nan', '']: curr_comm = c1
            elif pd.notna(c2) and str(c2).strip() not in ['nan', '']: curr_comm = c2
            
            status_lower = str(status).lower()
            if curr_comm == "-":
                comm_match = re.search(r'referred to (?:committee on|the committee on)?\s?([a-z\s&]+)', status_lower)
                if comm_match:
                    curr_comm = comm_match.group(1).title().strip()
            
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
    sheet_df = sheet_df.drop_duplicates(subset=['Bill Number'])
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")
except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

# 2. FETCH LIS DATA
lis_data = fetch_lis_data()
bills_to_track = sheet_df['Bill Number'].unique().tolist()

# 2b. FETCH WEB SCHEDULE (HYBRID MODE)
web_schedule_map = fetch_schedule_from_web()

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

    # --- TAB 3: UPCOMING (REWRITTEN: SCRAPER DRIVEN) ---
    with tab_upcoming:
        st.subheader("📅 Your Weekly Calendar")
        
        # We NO LONGER rely on 'full_schedule' CSV because it's empty/broken for 2026.
        # Instead, we iterate the Next 7 Days and check the SCRAPER MAP.

        today = datetime.now().date()
        cols = st.columns(7)
        my_bills = [b.upper() for b in bills_to_track]
        
        # Helper: Brain Dictionary
        bill_to_comm_map = final_df.set_index('Bill Number')['Current_Committee'].to_dict()
        bill_to_sub_map = final_df.set_index('Bill Number')['Current_Sub'].to_dict()
        bill_to_status_map = final_df.set_index('Bill Number')['Status'].to_dict()

        for i in range(7):
            target_date = today + timedelta(days=i)
            target_date_str = target_date.strftime('%Y-%m-%d')
            display_date_str = target_date.strftime("%a %m/%d")
            
            with cols[i]:
                st.markdown(f"**{display_date_str}**")
                st.divider()
                
                # Check if we have ANY scraped meetings for this date
                # web_schedule_map keys are (Date, CommitteeName)
                
                todays_meetings = {k[1]: v for k, v in web_schedule_map.items() if k[0] == target_date_str}
                
                bills_found_today = False
                
                if todays_meetings:
                    for bill in my_bills:
                        # 1. Get Bill Info
                        raw_comm = bill_to_comm_map.get(bill, '')
                        raw_sub = bill_to_sub_map.get(bill, '')
                        
                        clean_comm = normalize_text(raw_comm).replace("committee", "").strip()
                        clean_sub = normalize_text(raw_sub).replace("subcommittee", "").replace("sub", "").strip()
                        
                        # 2. Check for Match in Today's Meetings
                        match_time = None
                        match_comm_name = None
                        
                        for scraper_comm, scraper_time in todays_meetings.items():
                            # MATCH LOGIC:
                            # A. Sub Match (Strongest)
                            if len(clean_sub) > 3 and (clean_sub in scraper_comm or scraper_comm in clean_sub):
                                match_time = scraper_time
                                match_comm_name = scraper_comm
                                break
                            
                            # B. Main Committee Match (Weaker, check overlap)
                            # Only if scraper_comm is generic enough or matches well
                            tokens_bill = set(clean_comm.split())
                            tokens_scraper = set(scraper_comm.split())
                            ignore = {'and', 'the', 'of', 'committee', 'subcommittee', 'sub', 'house', 'senate'}
                            tokens_bill = {t for t in tokens_bill if t not in ignore}
                            tokens_scraper = {t for t in tokens_scraper if t not in ignore}
                            
                            if len(tokens_bill) > 0 and tokens_bill.issubset(tokens_scraper):
                                match_time = scraper_time
                                match_comm_name = scraper_comm
                                break
                        
                        if match_time:
                            bills_found_today = True
                            st.error(f"**{bill}**")
                            st.write(f"🏛️ **{match_comm_name.title()}**")
                            if raw_sub and raw_sub != '-': st.caption(f"↳ {raw_sub}")
                            st.caption(f"⏰ {match_time}")
                            st.divider()

                if not bills_found_today:
                    st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("Take a screenshot of this box!")
        
        # 1. Check if we scraped anything
        debug_data = st.session_state.get('debug_data', {})
        logs = debug_data.get('log', [])
        keys = debug_data.get('map_keys', [])
        
        st.write(f"**Scraper Status:** {'🟢 Active' if keys else '🔴 Empty'}")
        st.write(f"**Items Found:** {len(keys)}")
        
        # 2. Show what the 'Brain' is trying to match
        st.markdown("---")
        st.write("**Target Date (Today + 1):**")
        target_debug = (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')
        st.code(target_debug)
        
        st.write("**Available Keys for Target Date:**")
        relevant_keys = [k[1] for k in keys if k[0] == target_debug]
        if relevant_keys:
            st.json(relevant_keys)
        else:
            st.warning(f"No times found for {target_debug}")

        # 3. Show Raw Scraper Log (First 15 lines)
        st.markdown("---")
        st.write("**Scraper Log (First 15 lines):**")
        st.text("\n".join(logs[:15]))
