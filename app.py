import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import pytz # For EST Timezone
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
BILLS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
SUBS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Subscribers"

# --- VIRGINIA LIS DATA FEEDS (The "Public Website" Data) ---
# 20261 = 2026 Regular Session
LIS_BASE_URL = "https://lis.blob.core.windows.net/lisfiles/20261/"
LIS_BILLS_CSV = LIS_BASE_URL + "BILLS.csv"      # Status & Titles
LIS_DOCKET_CSV = LIS_BASE_URL + "SUBDOCKET.csv" # Upcoming Hearings

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
    "🌳 Environment & Energy": ["energy", "water", "pollution", "environment", "climate", "solar", "conservation", "waste", "carbon", "natural resources"],
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
    """Downloads the official LIS CSV files for Bills and Dockets."""
    data = {}
    
    # 1. Fetch Bills
    try:
        df_bills = pd.read_csv(LIS_BILLS_CSV, encoding='ISO-8859-1')
        # LIS Columns: Bill_id, Bill_description, Patron_name, Last_house_action, Last_house_action_date, etc.
        # Normalize column names
        df_bills.columns = df_bills.columns.str.strip().str.lower()
        # Create a unified 'status' column
        # LIS separates House/Senate actions. We'll grab the most recent one we can find.
        # Usually 'last_house_action' or 'last_senate_action'.
        # For simplicity, we'll combine them or prioritize one.
        
        # We need a clean bill number key
        df_bills['bill_clean'] = df_bills['bill_id'].astype(str).str.upper().str.strip()
        data['bills'] = df_bills
    except Exception as e:
        print(f"LIS Bill Fetch Error: {e}")
        data['bills'] = pd.DataFrame()

    # 2. Fetch Docket
    try:
        df_docket = pd.read_csv(LIS_DOCKET_CSV, encoding='ISO-8859-1')
        df_docket.columns = df_docket.columns.str.strip().str.lower()
        if 'bill_id' in df_docket.columns:
            df_docket['bill_clean'] = df_docket['bill_id'].astype(str).str.upper().str.strip()
        data['docket'] = df_docket
    except Exception as e:
        data['docket'] = pd.DataFrame()
        
    return data

def get_bill_data_batch(bill_numbers, lis_df):
    """Matches user bill numbers against the downloaded LIS database."""
    results = []
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))
    
    if lis_df.empty:
        # Fallback if LIS download failed
        for b in clean_bills:
             results.append({"Bill Number": b, "Status": "LIS Connection Error", "Lifecycle": "🚀 Active", "Official Title": "Error"})
        return pd.DataFrame(results)

    # Convert LIS df to dictionary for O(1) lookup
    # We index by 'bill_clean'
    lis_lookup = lis_df.set_index('bill_clean').to_dict('index')

    for bill_num in clean_bills:
        item = lis_lookup.get(bill_num)
        
        if item:
            # Found in LIS!
            # Determine Status: LIS has 'last_house_action' and 'last_senate_action'.
            # We pick the one with the later date, or just combine them.
            status = item.get('last_house_action', '')
            if pd.isna(status) or status == '':
                 status = item.get('last_senate_action', 'Introduced')
            
            # If both exist, we might want the most recent.
            # For now, let's trust 'last_house_action' if the bill started in House, etc.
            # Better: Just use the non-empty one.
            
            title = item.get('bill_description', 'No Title')
            
            results.append({
                "Bill Number": bill_num,
                "Official Title": title,
                "Status": str(status),
                "Date": str(item.get('last_house_action_date', '')), # Simple date string
                "Lifecycle": determine_lifecycle(str(status)),
                "Auto_Folder": get_smart_subject(title)
            })
        else:
            # Not found in LIS (Likely typo or very new)
            results.append({
                "Bill Number": bill_num, 
                "Status": "Not Found on LIS", 
                "Lifecycle": "🚀 Active", 
                "Official Title": "Unknown"
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
        alert_str = f"*{row['Bill Number']}*: {row.get('Status')}"
        if alert_str in history_text: continue
        updates_found = True
        report += f"\n⚪ {alert_str}"

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
        st.cache_data.clear() # Force clear cache to get fresh CSV
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
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper()
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
        # Mock Data Generator
        import random
        mock_results = []
        for b in bills_to_track:
            mock_t = random.choice(["Min Wage Act", "Rent Control", "Solar Rights"])
            mock_s = "Referred to Committee on Commerce and Labor"
            mock_results.append({
                "Bill Number": b, "Official Title": f"[DEMO] {mock_t}", "Status": mock_s,
                "Lifecycle": "🚀 Active", "Auto_Folder": get_smart_subject(mock_t)
            })
        api_df = pd.DataFrame(mock_results)
    else:
        api_df = get_bill_data_batch(bills_to_track, lis_data['bills'])

    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # Backup Categorization
    def assign_folder(row):
        title_to_check = row.get('Official Title', '')
        if str(title_to_check) in ["Unknown", "Error", "Not Found", "nan", "None", ""]:
            title_to_check = row.get('My Title', '')
        return get_smart_subject(str(title_to_check))

    if 'Auto_Folder' not in final_df.columns or final_df['Auto_Folder'].isnull().any():
         final_df['Auto_Folder'] = final_df.apply(assign_folder, axis=1)

    # Run Alerts
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
                st.dataframe(active[['Bill Number', 'Status']], hide_index=True, use_container_width=True)
            with m2:
                st.markdown("#### 🎉 Passed")
                passed_all = pd.concat([awaiting, signed])
                st.dataframe(passed_all[['Bill Number', 'Status']], hide_index=True, use_container_width=True)
            with m3:
                st.markdown("#### ❌ Failed")
                st.dataframe(dead[['Bill Number', 'Status']], hide_index=True, use_container_width=True)

    # --- TAB 3: UPCOMING ---
    with tab_upcoming:
        st.subheader("📅 Committee Dockets (Next 7 Days)")
        docket_df = lis_data.get('docket', pd.DataFrame())
        
        if docket_df.empty:
            st.info("No docket data available.")
        else:
            my_bills = [b.upper() for b in bills_to_track]
            if 'bill_clean' in docket_df.columns:
                my_upcoming = docket_df[docket_df['bill_clean'].isin(my_bills)]
                if not my_upcoming.empty:
                    st.success(f"⚠️ We found {len(my_upcoming)} of your bills on the agenda!")
                    st.dataframe(my_upcoming, hide_index=True)
                else:
                    st.info("None of your tracked bills are on the current dockets.")
                with st.expander("See Full Public Docket"):
                    st.dataframe(docket_df)
            else:
                st.warning("Docket format error.")
