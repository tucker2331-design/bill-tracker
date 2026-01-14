import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
BILLS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
SUBS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Subscribers"
# Official LIS Docket File (2026 Regular Session)
DOCKET_URL = "https://lis.blob.core.windows.net/lisfiles/20261/SUBDOCKET.csv"

API_KEY = st.secrets.get("OPENSTATES_API_KEY")

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- EXPANDED SMART CATEGORIZATION ---
TOPIC_KEYWORDS = {
    "🗳️ Elections & Democracy": ["election", "vote", "ballot", "campaign", "poll", "voter", "registrar", "districting", "suffrage"],
    "🏗️ Housing & Property": ["rent", "landlord", "tenant", "housing", "lease", "property", "zoning", "eviction", "homeowner", "development", "residential"],
    "✊ Labor & Workers Rights": ["wage", "salary", "worker", "employment", "labor", "union", "bargaining", "leave", "compensation", "workplace", "employee"],
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

def get_smart_subject(title, api_subjects):
    title_lower = str(title).lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    if api_subjects and len(api_subjects) > 0:
        return api_subjects[0]
    return "📂 Unassigned / General"

# --- DATA FETCHING ---
@st.cache_data(ttl=300) 
def get_upcoming_hearings():
    try:
        df = pd.read_csv(DOCKET_URL, encoding='ISO-8859-1')
        df.columns = df.columns.str.strip().str.lower()
        return df
    except:
        return pd.DataFrame()

def get_bill_data_batch(bill_numbers):
    results = []
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))
    
    if not clean_bills: return pd.DataFrame()

    chunk_size = 20
    chunks = [clean_bills[i:i + chunk_size] for i in range(0, len(clean_bills), chunk_size)]
    
    progress_bar = st.progress(0, text="Connecting to VA Legislature...")
    total_processed = 0
    
    for chunk in chunks:
        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia", "session": "2026", "identifier": chunk,
            "include": ["actions", "sponsorships", "abstracts"], "apikey": API_KEY, "per_page": 50
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            found_data = {b['identifier'].upper(): b for b in data.get('results', [])}

            for bill_num in chunk:
                item = found_data.get(bill_num)
                if item:
                    latest_action = item['actions'][0]['description'] if item['actions'] else "Introduced"
                    smart_folder = get_smart_subject(item['title'], item.get('subject', []))
                    results.append({
                        "Bill Number": bill_num,
                        "Official Title": item['title'],
                        "Status": latest_action,
                        "Date": item['actions'][0]['date'] if item['actions'] else "",
                        "Auto_Folder": smart_folder,
                        "Lifecycle": determine_lifecycle(latest_action),
                        "History": item['actions']
                    })
                else:
                    results.append({
                        "Bill Number": bill_num, "Status": "Not Found / Prefiled",
                        "Lifecycle": "🚀 Active", "Auto_Folder": "📂 Unassigned / General"
                    })
        except:
            for b in chunk:
                results.append({"Bill Number": b, "Status": "⚠️ API Error (Wait)", "Lifecycle": "🚀 Active", "Auto_Folder": "⚠️ System Alert"})
        
        total_processed += len(chunk)
        progress_bar.progress(total_processed / len(clean_bills))

    progress_bar.empty()
    return pd.DataFrame(results)

# --- ALERTS & SIDEBAR STATUS ---
def check_and_broadcast(df_bills, df_subscribers):
    st.sidebar.header("🤖 Slack Bot Status")
    
    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token: 
        st.sidebar.error("❌ Token Missing")
        return

    client = WebClient(token=token)
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
        if not subscriber_list: 
            st.sidebar.warning("⚠️ No Subscribers")
            return
        
        # Check history of first user
        user_id = client.users_lookupByEmail(email=subscriber_list[0].strip())['user']['id']
        history = client.conversations_history(channel=client.conversations_open(users=[user_id])['channel']['id'], limit=100)
        history_text = "\n".join([m.get('text', '') for m in history['messages']])
        
        st.sidebar.success("✅ Connected to Slack")
        st.sidebar.caption(f"Monitoring for {len(subscriber_list)} users")
        
    except Exception as e:
        st.sidebar.error(f"❌ Connection Error: {e}")
        return

    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n_Latest changes detected:_\n"
    updates_found = False
    
    for i, row in df_bills.iterrows():
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
        st.sidebar.info("📢 Update Sent!")
    else:
        st.sidebar.success("✅ Up to Date (No new changes)")

# --- UI COMPONENTS ---
def render_bill_card(row):
    title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', 'Loading...')
    st.markdown(f"**{row['Bill Number']}**")
    st.caption(f"{title}")
    st.caption(f"_{row.get('Status')}_")
    st.divider()

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")

# Initialize Session State for Timer
if 'last_run' not in st.session_state:
    st.session_state['last_run'] = datetime.now().strftime("%I:%M %p")

# Refresh Button & Timer Layout
col_btn, col_time = st.columns([1, 6])
with col_btn:
    if st.button("🔄 Check for Updates"):
        st.session_state['last_run'] = datetime.now().strftime("%I:%M %p")
        st.rerun()
with col_time:
    st.markdown(f"**Last Refreshed:** `{st.session_state['last_run']}`")

# 1. LOAD DATA
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

# 2. FETCH API DATA
bills_to_track = sheet_df['Bill Number'].unique().tolist()
if bills_to_track:
    api_df = get_bill_data_batch(bills_to_track)
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # Run Alerts (Populates Sidebar)
    check_and_broadcast(final_df, subs_df)

    # 3. RENDER TABS
    tab_involved, tab_watching, tab_upcoming = st.tabs(["🚀 Directly Involved", "👀 Watching", "📅 Upcoming Hearings"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            
            # --- TOP SECTION: BY TOPIC (GRID LAYOUT) ---
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

            # --- BOTTOM SECTION: MASTER LIST (STATUS) ---
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

    # --- TAB 3: UPCOMING (DOCKET) ---
    with tab_upcoming:
        st.subheader("📅 Committee Dockets (Next 7 Days)")
        docket_df = get_upcoming_hearings()
        
        if docket_df.empty:
            st.info("No docket data available (Session may not have started).")
        else:
            my_bills = [b.upper() for b in bills_to_track]
            if 'bill_id' in docket_df.columns:
                docket_df['bill_id_clean'] = docket_df['bill_id'].astype(str).str.upper().str.strip()
                my_upcoming = docket_df[docket_df['bill_id_clean'].isin(my_bills)]
                
                if not my_upcoming.empty:
                    st.success(f"⚠️ We found {len(my_upcoming)} of your bills on the agenda!")
                    st.dataframe(my_upcoming, hide_index=True)
                else:
                    st.info("None of your tracked bills are on the current dockets.")
                
                with st.expander("See Full Public Docket"):
                    st.dataframe(docket_df)
            else:
                st.warning("Docket file format unavailable.")
