import streamlit as st
import pandas as pd
import requests
import time
import re
import concurrent.futures # For speed (Parallel Scraping)
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

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- HELPER FUNCTIONS ---
def clean_committee_name(name):
    if not name or str(name).lower() in ['nan', '-', 'none', '']: return ""
    name = str(name).strip()
    if "," in name: name = name.split(",")[0].strip()

    mapping = {
        "HED": "House Education", "HEDC": "House Education",
        "P&E": "Privileges & Elections", "C&L": "Commerce & Labor",
        "HWI": "House Health, Welfare & Inst.", "APP": "House Appropriations",
        "HAPP": "House Appropriations", "FIN": "Senate Finance & Appropriations",
        "JUD": "Courts of Justice", "GL": "General Laws",
        "AG": "Agriculture", "TRAN": "Transportation",
        "SFIN": "Senate Finance & Appropriations", "HFIN": "House Finance",
        "SEH": "Senate Education & Health", "CL": "Commerce & Labor",
        "SCL": "Senate Commerce & Labor", "HCL": "House Commerce & Labor"
    }
    
    upper_name = name.upper()
    if upper_name in mapping: return mapping[upper_name]

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

def determine_lifecycle(status_text, committee_name):
    # Sticky Logic: If we have a committee, we are IN COMMITTEE unless explicitly moved out
    status = str(status_text).lower()
    comm = str(committee_name).strip()
    
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]):
        return "✅ Signed & Enacted"
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]):
        return "❌ Dead / Tabled"
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]):
        return "✍️ Awaiting Signature"
        
    exit_keywords = ["reported", "read", "passed", "agreed", "engrossed", "calendar", "candidate", "communicated"]
    has_committee = comm not in ["-", "nan", "None", ""]
    is_exiting = any(x in status for x in exit_keywords)
    
    if has_committee and not is_exiting:
        return "📥 In Committee"

    if any(x in status for x in ["referred", "assigned", "continued", "committee"]):
        return "📥 In Committee"
        
    return "📣 Out of Committee"

def get_smart_subject(title):
    title_lower = str(title).lower()
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
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    return "📂 Unassigned / General"

def normalize_text_strict(t):
    if pd.isna(t): return ""
    t = str(t).lower().replace('&','and').replace('.','').replace(',','').replace('-',' ')
    return " ".join(t.split())

def clean_status_text(text):
    if not text: return ""
    text = str(text)
    replacements = {
        "HED": "House Education", "HAPP": "House Appropriations",
        "sub:": "Subcommittee:", "P&E": "Privileges & Elections",
        "C&L": "Commerce & Labor", "floor offered": "Floor Amendment Offered",
        "passed by indefinitely": "Passed By Indefinitely (Dead)"
    }
    for abbr, full in replacements.items():
        pattern = re.compile(re.escape(abbr), re.IGNORECASE)
        text = pattern.sub(full, text)
    return text

# --- CORE LOGIC: SINGLE BILL SCRAPER ---
# This runs inside the threads
def scrape_single_bill(bill_num, csv_info):
    url = f"https://lis.virginia.gov/cgi-bin/legp604.exe?261+sum+{bill_num}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # Defaults from CSV (Fast Fallback)
    status = csv_info.get('last_house_action', csv_info.get('last_senate_action', 'Introduced'))
    if pd.isna(status): status = "Introduced"
    
    # Basic data
    details = {
        "status": str(status),
        "history": [],
        "committee": "-"
    }
    
    try:
        # Request LIS Page
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # Find History Table
            history_rows = []
            history_header = soup.find('h4', string=re.compile('History'))
            if history_header:
                history_table = history_header.find_next('table')
                if history_table:
                    rows = history_table.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 2:
                            d = cols[0].get_text(strip=True)
                            a = cols[1].get_text(strip=True)
                            history_rows.append({"Date": d, "Action": a})
            
            details['history'] = history_rows
            
            # Update Status if we found history (Top row is newest)
            if history_rows:
                details['status'] = history_rows[0]['Action']
                
                # STICKY COMMITTEE SEARCH
                # Look backwards through history for "Referred to"
                for row in history_rows:
                    action = row['Action'].lower()
                    if "referred to committee" in action:
                        match = re.search(r'committee (?:on|for) (.+)', action, re.IGNORECASE)
                        if match:
                            raw_comm = match.group(1).split("(")[0]
                            chamber = "House" if bill_num.upper().startswith("H") else "Senate"
                            clean_comm = clean_committee_name(raw_comm)
                            # Fix missing chamber prefix
                            if "House" not in clean_comm and "Senate" not in clean_comm:
                                clean_comm = f"{chamber} {clean_comm}"
                            details['committee'] = clean_comm
                            break
    except:
        pass # If fail, return CSV defaults
        
    return details

# --- BATCH PROCESSOR (PARALLEL) ---
def get_bill_data_batch(bill_numbers, lis_df):
    clean_bills = list(set([str(b).strip().upper().replace(" ", "") for b in bill_numbers if str(b).strip() != 'nan']))
    
    # Index CSV for fast lookup
    lis_lookup = {}
    if not lis_df.empty:
        lis_lookup = lis_df.set_index('bill_clean').to_dict('index')

    results = []
    
    # Helper for the ThreadPool
    def worker(b_num):
        csv_data = lis_lookup.get(b_num, {})
        scraped = scrape_single_bill(b_num, csv_data)
        
        # Merge Scraped Data + CSV Titles
        title = csv_data.get('bill_description', 'No Title')
        
        # Date Logic
        date_val = ""
        if scraped['history']:
            date_val = scraped['history'][0]['Date']
        else:
            # Fallback Date
            date_val = str(csv_data.get('last_house_action_date', ''))
            
        lifecycle = determine_lifecycle(scraped['status'], scraped['committee'])
        
        return {
            "Bill Number": b_num,
            "Official Title": title,
            "Status": scraped['status'], # From Scraper
            "Date": date_val, 
            "Lifecycle": lifecycle,
            "Auto_Folder": get_smart_subject(title),
            "History_Data": scraped['history'],
            "Current_Committee": scraped['committee'],
            "Current_Sub": "-"
        }

    # Run Parallel (10 workers)
    # This keeps the UI responsive
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_bill = {executor.submit(worker, b): b for b in clean_bills}
        
        # Optional: Add a spinner/progress if you want, but this runs fast enough usually
        for future in concurrent.futures.as_completed(future_to_bill):
            try:
                res = future.result()
                results.append(res)
            except:
                pass

    return pd.DataFrame(results)

# --- SCHEDULE SCRAPER (ORIGINAL) ---
@st.cache_data(ttl=600)
def fetch_schedule_from_web():
    schedule_map = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    urls = [
        ("https://apps.senate.virginia.gov/Senator/ComMeetings.php", "Senate"),
        ("https://house.vga.virginia.gov/schedule/meetings", "House")
    ]

    for url, chamber in urls:
        try:
            resp = requests.get(url, headers=headers, timeout=5)
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
                                if "View Agenda" in comm_name: 
                                    if i > 1: comm_name = lines[i-2]

                                clean_name = normalize_text_strict(comm_name)
                                if "senate" not in clean_name and "house" not in clean_name:
                                    clean_name = f"{chamber.lower()} {clean_name}"
                                clean_name = clean_name.replace("senate", "").replace("house", "").strip()
                                
                                key = (date_str, clean_name)
                                display_name = clean_committee_name(comm_name)
                                if chamber not in display_name: display_name = f"{chamber} {display_name}"
                                schedule_map[key] = (time_val, display_name)
                        except: pass
        except: pass
    return schedule_map

# --- DATA FETCHING (CSV) ---
@st.cache_data(ttl=300) 
def fetch_lis_data():
    data = {}
    try:
        df = pd.read_csv(LIS_BILLS_CSV, encoding='ISO-8859-1')
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_').str.replace('/', '_').str.replace('.', '')
        if 'bill_id' in df.columns:
            df['bill_clean'] = df['bill_id'].astype(str).str.upper().str.replace(" ", "").str.strip()
            data['bills'] = df
        else: data['bills'] = pd.DataFrame() 
    except: data['bills'] = pd.DataFrame()
    return data

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
        raw_history_text = "\n".join([m.get('text', '') for m in history['messages']])
        history_text = raw_history_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        st.sidebar.success(f"✅ Connected to Slack")
    except Exception as e:
        st.sidebar.error(f"❌ Slack Error: {e}")
        return

    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n_Latest changes detected:_\n"
    updates_found = False
    
    for i, row in df_bills.iterrows():
        if "LIS Connection Error" in str(row.get('Status')): continue
        b_num = str(row['Bill Number']).strip()
        raw_status = str(row.get('Status', 'No Status')).strip()
        clean_status = clean_status_text(raw_status)
        
        if b_num in history_text and clean_status in history_text: continue
        
        display_name = str(row.get('My Title', '-'))
        if display_name == "-" or display_name == "nan" or not display_name:
            official = str(row.get('Official Title', ''))
            display_name = (official[:60] + '..') if len(official) > 60 else official
            
        updates_found = True
        report += f"\n⚪ *{b_num}* | {display_name}\n> _{clean_status}_\n"

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
    
    if row['Lifecycle'] == "📥 In Committee":
        st.markdown(f"🏛️ **{row['Current_Committee']}**")

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
        if my_status and my_status != 'nan' and my_status != '-': label_text += f" - {my_status}"
        if header_title: label_text += f" - {header_title}"
        
        with st.expander(label_text):
            st.markdown(f"**🏛️ Current Committee:** {clean_committee_name(row.get('Current_Committee', '-'))}")
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
        # PARALLEL FETCHING
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

    # --- TAB 3: UPCOMING ---
    with tab_upcoming:
        st.subheader("📅 Your Confirmed Agenda")
        
        # FIXED: Use EST for today calculation
        today = datetime.now(est).date()
        cols = st.columns(7)
        
        schedule_df = lis_data.get('schedule', pd.DataFrame())
        my_bills_clean = [b.upper().strip() for b in bills_to_track]
        
        confirmed_bills_set = set()
        if not schedule_df.empty:
            matches = schedule_df[schedule_df['bill_clean'].isin(my_bills_clean)]
            confirmed_bills_set = set(matches['bill_clean'].unique())

        bill_info_map = final_df.set_index('Bill Number')[['Current_Committee', 'Current_Sub', 'My Status', 'Status', 'Date']].to_dict('index')

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
                        for b_id in confirmed_bills_set:
                            if b_id in bills_shown_today: continue 

                            info = bill_info_map.get(b_id, {})
                            curr_comm = normalize_text_strict(info.get('Current_Committee', ''))
                            curr_sub = normalize_text_strict(info.get('Current_Sub', ''))
                            
                            match = False
                            if curr_comm and len(curr_comm) > 2:
                                if curr_comm in scraper_clean_name or scraper_clean_name in curr_comm: match = True
                            if curr_sub and len(curr_sub) > 2:
                                if curr_sub in scraper_clean_name or scraper_clean_name in curr_sub: match = True
                                    
                            if match:
                                matched_bills.append(b_id)
                                bills_shown_today.add(b_id)

                        if matched_bills:
                            events_found = True
                            header_display = clean_committee_name(scraper_full_name)
                            sub_display = None
                            if "—" in scraper_full_name:
                                parts = scraper_full_name.split("—")
                                sub_display = parts[1].strip()
                            elif "Subcommittee" in scraper_full_name:
                                match = re.search(r'(.+?)\s+(Subcommittee.*)', scraper_full_name, re.IGNORECASE)
                                if match: sub_display = match.group(2).strip()

                            st.markdown(f"**{header_display}**")
                            if sub_display: st.markdown(f"↳ _{sub_display}_")
                            st.caption(f"⏰ {scraper_time}")
                            
                            for b_id in matched_bills:
                                info = bill_info_map.get(b_id, {})
                                status_text = ""
                                raw_status = str(info.get('My Status', '')).strip()
                                if raw_status and raw_status != 'nan' and raw_status != '-':
                                    status_text = f" - {raw_status}"
                                st.error(f"**{b_id}**{status_text}")
                            
                            st.divider()

                if i == 0: 
                    history_groups = {}
                    for b_id, info in bill_info_map.items():
                        if b_id in bills_shown_today: continue
                        
                        last_date = str(info.get('Date', ''))
                        is_today = False
                        if last_date == target_date_str: is_today = True
                        else:
                            try:
                                lis_dt = datetime.strptime(last_date, "%m/%d/%Y").date()
                                if lis_dt == target_date: is_today = True
                            except: pass

                        if is_today:
                            lis_status = str(info.get('Status', ''))
                            skip_keywords = ["referred", "printed", "presentation", "reading waived"]
                            is_outcome = any(x in lis_status.lower() for x in ["reported", "passed", "defeat", "stricken", "agreed", "read", "engross", "vote", "assigned"])
                            is_admin = any(x in lis_status.lower() for x in skip_keywords)
                            if is_admin and not is_outcome: continue

                            events_found = True
                            bills_shown_today.add(b_id)
                            
                            raw_comm = str(info.get('Current_Committee', ''))
                            if raw_comm in ["-", "nan", "None", ""]: raw_comm = ""
                            
                            if "fiscal" in lis_status.lower(): group_name = "Fiscal Impact Report"
                            elif b_id.startswith(("HJ", "SJ", "HR", "SR")): group_name = "Floor Session"
                            elif not raw_comm:
                                if any(x in lis_status.lower() for x in ["read", "pass", "engross", "defeat"]): group_name = "Floor Session / Action"
                                else: group_name = "General Assembly Action"
                            else:
                                group_name = clean_committee_name(raw_comm)
                                if group_name == "Education":
                                    if b_id.startswith("HB") or b_id.startswith("HJ"): group_name = "House Education"
                                    elif b_id.startswith("SB") or b_id.startswith("SJ"): group_name = "Senate Education & Health"
                            
                            if group_name not in history_groups: history_groups[group_name] = []
                            history_groups[group_name].append(b_id)

                    for g_name, b_list in history_groups.items():
                        st.markdown(f"**{g_name}**")
                        st.caption("⏰ Completed / Actioned")
                        for b_id in b_list:
                            info = bill_info_map.get(b_id, {})
                            status_text = ""
                            raw_status = str(info.get('My Status', '')).strip()
                            if raw_status and raw_status != 'nan' and raw_status != '-':
                                status_text = f" - {raw_status}"
                            st.error(f"**{b_id}**{status_text}")
                            st.caption(f"_{clean_status_text(info.get('Status'))}_")
                        st.divider()

                if not events_found:
                    st.caption("-")

# --- DEV DEBUGGER ---
with st.sidebar:
    st.divider()
    with st.expander("👨‍💻 Developer Debugger", expanded=True):
        st.write("Take a screenshot of this box!")
        debug_data = st.session_state.get('debug_data', {})
        logs = debug_data.get('log', [])
        keys = debug_data.get('map_keys', [])
        st.write(f"**Scraper Status:** {'🟢 Active' if keys else '🔴 Empty'}")
        st.write(f"**Items Found:** {len(keys)}")
        st.write("**Scraper Log (First 15 lines):**")
        st.text("\n".join(logs[:15]))
