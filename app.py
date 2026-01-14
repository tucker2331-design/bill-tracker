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

# Virginia LIS Official Data File (Updates Hourly)
# 20261 = 2026 Regular Session
DOCKET_URL = "https://lis.blob.core.windows.net/lisfiles/20261/SUBDOCKET.csv"

API_KEY = st.secrets.get("OPENSTATES_API_KEY")

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- SMART CATEGORIZATION ---
TOPIC_KEYWORDS = {
    "Economy & Labor": ["wage", "salary", "worker", "employment", "labor", "business", "tax", "commerce", "job", "pay"],
    "Education": ["school", "education", "student", "university", "college", "teacher", "curriculum", "scholarship"],
    "Public Safety & Law": ["firearm", "gun", "police", "crime", "penalty", "court", "judge", "enforcement", "prison", "arrest"],
    "Health": ["health", "medical", "hospital", "patient", "doctor", "insurance", "care", "mental"],
    "Environment": ["energy", "water", "pollution", "environment", "climate", "solar", "conservation", "waste"],
    "Housing": ["rent", "landlord", "tenant", "housing", "lease", "property", "zoning", "eviction"],
    "Transportation": ["road", "highway", "vehicle", "driver", "license", "transit", "traffic"]
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
    return "General / Unsorted"

# --- NEW: UPCOMING DOCKET FETCH ---
@st.cache_data(ttl=3600) # Cache for 1 hour
def get_upcoming_hearings():
    try:
        # Load the official CSV from LIS
        df = pd.read_csv(DOCKET_URL, encoding='ISO-8859-1')
        
        # Clean Columns (LIS headers are sometimes messy)
        # Expected: Bill_id, Committee_name, Meeting_date, etc.
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        # If file doesn't exist yet (early session), return empty
        return pd.DataFrame()

# --- OPTIMIZED: BULK BILL FETCH (TURBO MODE) ---
def get_bill_data_batch(bill_numbers):
    results = []
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))
    
    if not clean_bills:
        return pd.DataFrame()

    # 1. NEW LOGIC: ONE REQUEST for all bills
    # "Chunking" into groups of 50 to be safe, but usually 1 call works.
    
    progress_bar = st.progress(0, text="Connecting to VA Legislature (Bulk Mode)...")
    
    # We will query: identifier__in=HB1,HB2,HB3...
    chunk_size = 20 # OpenStates handles about 20-50 comfortably in url
    chunks = [clean_bills[i:i + chunk_size] for i in range(0, len(clean_bills), chunk_size)]
    
    total_processed = 0
    
    for chunk in chunks:
        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia", 
            "session": "2026", 
            "identifier": chunk, # This passes multiple ?identifier=HB1&identifier=HB2...
            "include": ["actions", "sponsorships", "abstracts"], 
            "apikey": API_KEY,
            "per_page": 50
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            # Create a dictionary for quick lookup of the results
            found_data = {b['identifier'].upper(): b for b in data.get('results', [])}

            # Loop through OUR list to preserve order and handle missing ones
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
                        "Sponsor": item['sponsorships'][0]['name'] if item['sponsorships'] else "Unknown",
                        "Auto_Folder": smart_folder,
                        "History": item['actions'],
                        "Lifecycle": determine_lifecycle(latest_action)
                    })
                else:
                    # Bill not found in API (yet)
                    results.append({
                        "Bill Number": bill_num, 
                        "Status": "Not Found / Prefiled", 
                        "Lifecycle": "🚀 Active",
                        "Auto_Folder": "Unassigned"
                    })

        except Exception as e:
            # Fallback for error
            for b in chunk:
                results.append({"Bill Number": b, "Status": "API Error", "Lifecycle": "🚀 Active"})
        
        total_processed += len(chunk)
        progress_bar.progress(total_processed / len(clean_bills), text=f"scanned {total_processed} bills...")

    progress_bar.empty()
    return pd.DataFrame(results)

# --- HISTORY CHECK & BROADCAST ---
def check_and_broadcast(df_bills, df_subscribers):
    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token: return

    client = WebClient(token=token)
    
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
    except KeyError:
        return

    if not subscriber_list: return

    combined_history_text = ""
    first_email = subscriber_list[0].strip()
    
    try:
        lookup = client.users_lookupByEmail(email=first_email)
        user_id = lookup['user']['id']
        dm_channel = client.conversations_open(users=[user_id])
        channel_id = dm_channel['channel']['id']
        history = client.conversations_history(channel=channel_id, limit=1000)
        
        if history['messages']:
            for msg in history['messages']:
                combined_history_text += msg.get('text', '') + "\n"
            
    except SlackApiError:
        return

    report = f"🏛️ *VA LEGISLATIVE UPDATE* - {datetime.now().strftime('%m/%d')}\n"
    report += "_Latest changes detected:_\n"
    
    updates_found = False
    
    for i, row in df_bills.iterrows():
        b_num = row['Bill Number']
        current_status = row.get('Status', 'Unknown')
        
        expected_alert_string = f"*{b_num}*: {current_status}"
        
        if expected_alert_string in combined_history_text:
            continue
            
        updates_found = True
        emoji = "⚪"
        if "Signed" in row['Lifecycle']: emoji = "✅"
        elif "Dead" in row['Lifecycle']: emoji = "❌"
        elif "Active" in row['Lifecycle']: emoji = "🚀"
        elif "Awaiting" in row['Lifecycle']: emoji = "✍️"
        
        report += f"\n{emoji} {expected_alert_string}"

    if updates_found:
        st.toast(f"📢 Broadcasting to {len(subscriber_list)} people...")
        for email in subscriber_list:
            try:
                lookup = client.users_lookupByEmail(email=email.strip())
                user_id = lookup['user']['id']
                client.chat_postMessage(channel=user_id, text=report)
            except SlackApiError:
                pass
        st.toast("✅ Update Broadcast Complete!")
    else:
        st.sidebar.success("✅ System Checked: No new updates.")

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")

try:
    raw_df = pd.read_csv(BILLS_URL)
    raw_df.columns = raw_df.columns.str.strip()
    
    try:
        subs_df = pd.read_csv(SUBS_URL)
        subs_df.columns = subs_df.columns.str.strip()
    except:
        subs_df = pd.DataFrame(columns=["Email"]) 

    if 'Bills Watching' in raw_df.columns:
        df_w = raw_df[['Bills Watching', 'Title (Watching)']].copy()
        df_w.columns = ['Bill Number', 'My Title']
        df_w['Type'] = 'Watching'
    else: df_w = pd.DataFrame()

    working_col = next((c for c in raw_df.columns if "Working On" in c), None)
    if working_col:
        df_i = raw_df[[working_col]].copy()
        df_i.columns = ['Bill Number']
        df_i['My Title'] = "-" 
        df_i['Type'] = 'Involved'
    else: df_i = pd.DataFrame()
        
    sheet_df = pd.concat([df_w, df_i], ignore_index=True)
    sheet_df = sheet_df.dropna(subset=['Bill Number'])
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper()
    sheet_df = sheet_df[sheet_df['Bill Number'] != 'NAN']
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")

except Exception as e:
    st.error(f"Sheet Error: {e}")
    st.stop()

if st.button("🔄 Check for Updates"):
    st.rerun()

bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    # 1. FETCH BILL DATA (OPTIMIZED)
    api_df = get_bill_data_batch(bills_to_track)
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # 2. RUN ALERTS
    check_and_broadcast(final_df, subs_df)
    
    # 3. FETCH UPCOMING HEARINGS (NEW)
    docket_df = get_upcoming_hearings()
    
    # --- HELPER FOR DRAWING SECTIONS ---
    def draw_categorized_section(bills, title, color_code):
        st.markdown(f"##### {color_code} {title} ({len(bills)})")
        if bills.empty:
            st.caption("No bills.")
            return

        subjects = sorted([s for s in bills['Auto_Folder'].unique() if str(s) != 'nan'])
        for subj in subjects:
            subset = bills[bills['Auto_Folder'] == subj]
            with st.expander(f"📁 {subj} ({len(subset)})", expanded=False):
                for i, row in subset.iterrows():
                    render_bill_card(row)

    def render_bill_card(row):
        display_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', 'Loading...')
        st.markdown(f"**{row['Bill Number']}:** {display_title}")
        st.caption(f"Status: {row.get('Status')} | Last Action: {row.get('Date', '-')}")
        
        history_data = row.get('History')
        if isinstance(history_data, list) and history_data:
            hist_df = pd.DataFrame(history_data)
            if 'date' in hist_df.columns and 'description' in hist_df.columns:
                st.dataframe(hist_df[['date', 'description']], hide_index=True, use_container_width=True)
        st.divider()

    # --- TABS ---
    tab_involved, tab_watching, tab_upcoming = st.tabs(["🚀 Directly Involved", "👀 Watching", "📅 Upcoming Hearings"])

    # --- TAB 1 & 2: STATUS ---
    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            
            active = subset[subset['Lifecycle'] == "🚀 Active"]
            awaiting = subset[subset['Lifecycle'] == "✍️ Awaiting Signature"]
            signed = subset[subset['Lifecycle'] == "✅ Signed & Enacted"]
            dead = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            c_active, c_passed, c_failed = st.columns(3)
            with c_active:
                draw_categorized_section(active, "Active", "🚀")
            with c_passed:
                st.markdown("##### 🎉 Passed Legislation")
                st.caption(f"Total: {len(awaiting) + len(signed)}")
                st.divider()
                st.markdown(f"**✍️ Awaiting Sig ({len(awaiting)})**")
                if not awaiting.empty:
                     for i, r in awaiting.iterrows(): render_bill_card(r)
                else: st.caption("No bills.")
                st.divider()
                st.markdown(f"**✅ Signed ({len(signed)})**")
                if not signed.empty:
                     for i, r in signed.iterrows(): render_bill_card(r)
                else: st.caption("No bills.")
            with c_failed:
                draw_categorized_section(dead, "Dead / Failed", "❌")
            
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            st.dataframe(subset[["Bill Number", "My Title", "Status", "Date"]], use_container_width=True)

    # --- TAB 3: UPCOMING HEARINGS (NEW) ---
    with tab_upcoming:
        st.subheader("📅 Next 7 Days: Committee Dockets")
        
        if docket_df.empty:
            st.info("No docket data available yet (Session hasn't started or LIS file is empty).")
        else:
            # Match Docket Bill_ID with Tracked Bills
            # LIS Bill IDs often look like "HB123". Our list is "HB123".
            # Clean both sides to be sure.
            
            my_bills = [b.upper() for b in bills_to_track]
            
            # Filter Docket for MY bills
            # Assuming column 'bill_id' exists in LIS csv
            if 'bill_id' in docket_df.columns:
                docket_df['bill_id_clean'] = docket_df['bill_id'].astype(str).str.upper().str.strip()
                
                my_upcoming = docket_df[docket_df['bill_id_clean'].isin(my_bills)]
                
                if not my_upcoming.empty:
                    st.success(f"⚠️ Found {len(my_upcoming)} of your bills on the agenda!")
                    # Display nice table
                    display_cols = ['meeting_date', 'bill_id', 'committee_name', 'time', 'room']
                    # Filter for cols that actually exist in the CSV
                    valid_cols = [c for c in display_cols if c in my_upcoming.columns]
                    st.dataframe(my_upcoming[valid_cols], hide_index=True)
                else:
                    st.info("None of your tracked bills are on the current dockets.")
                    
                with st.expander("View Full Public Docket (All Bills)"):
                    st.dataframe(docket_df)
            else:
                st.warning("Could not read LIS Docket format. Columns found: " + str(docket_df.columns))

    st.sidebar.success("✅ System Online")

else:
    st.info("Add bills to your Google Sheet.")
