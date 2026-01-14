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
    
    # 1. PASSED & SIGNED (Law)
    if any(x in status for x in ["signed by governor", "enacted", "approved by governor", "chapter"]):
        return "✅ Signed & Enacted"
    
    # 2. DEAD / FAILED
    if any(x in status for x in ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]):
        return "❌ Dead / Tabled"
    
    # 3. PASSED LEGISLATURE (Waiting on Governor)
    if any(x in status for x in ["enrolled", "communicated to governor", "bill text as passed"]):
        return "✍️ Awaiting Signature"
        
    # 4. ACTIVE
    return "🚀 Active"

def get_smart_subject(title, api_subjects):
    title_lower = str(title).lower()
    for category, keywords in TOPIC_KEYWORDS.items():
        if any(k in title_lower for k in keywords):
            return category
    if api_subjects and len(api_subjects) > 0:
        return api_subjects[0]
    return "General / Unsorted"

def get_bill_data_batch(bill_numbers):
    results = []
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))
    total = len(clean_bills)
    
    progress_bar = st.progress(0, text="Connecting to VA Legislature...")

    for i, bill_num in enumerate(clean_bills):
        if not bill_num: continue
        time.sleep(1.0) 
        progress_bar.progress((i + 1) / total, text=f"Checking {bill_num}...")

        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia", "session": "2026", "identifier": bill_num,
            "include": ["actions", "sponsorships", "abstracts"], "apikey": API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            if response.status_code != 200:
                results.append({"Bill Number": bill_num, "Status": "Error/Not Found", "Lifecycle": "Unknown"})
                continue

            data = response.json()
            if data['results']:
                item = data['results'][0]
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
                results.append({"Bill Number": bill_num, "Official Title": "Not Found", "Auto_Folder": "Unassigned", "Lifecycle": "Unknown"})
        except Exception as e:
            results.append({"Bill Number": bill_num, "Status": f"Error: {e}", "Auto_Folder": "Error", "Lifecycle": "Unknown"})
            
    progress_bar.empty()
    return pd.DataFrame(results)

# --- HISTORY CHECK & BROADCAST ---
def check_and_broadcast(df_bills, df_subscribers):
    token = st.secrets.get("SLACK_BOT_TOKEN")
    if not token:
        st.error("Missing SLACK_BOT_TOKEN.")
        return

    client = WebClient(token=token)
    
    try:
        subscriber_list = df_subscribers['Email'].dropna().unique().tolist()
    except KeyError:
        st.sidebar.warning("No 'Email' column in Subscribers tab.")
        return

    if not subscriber_list:
        return

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
            
    except SlackApiError as e:
        st.sidebar.error(f"Slack Error: {e}")
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
            except SlackApiError as e:
                st.sidebar.error(f"Failed to send to {email}: {e}")
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

    if 'Bills Working On' in raw_df.columns:
        df_i = raw_df[['Bills Working On', 'Title (Working)']].copy()
        df_i.columns = ['Bill Number', 'My Title']
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
    api_df = get_bill_data_batch(bills_to_track)
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    check_and_broadcast(final_df, subs_df)
    
    # --- HELPER FOR DRAWING SECTIONS ---
    def draw_categorized_section(bills, title, color_code):
        # ALWAYS SHOW HEADER (Even if empty)
        st.markdown(f"#### {color_code} {title} ({len(bills)})")
        
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

    st.subheader("🗂️ Categorized View")
    tab_involved, tab_watching = st.tabs(["🚀 Directly Involved", "👀 Watching"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            
            # --- LIFECYCLE BUCKETS ---
            active = subset[subset['Lifecycle'] == "🚀 Active"]
            awaiting = subset[subset['Lifecycle'] == "✍️ Awaiting Signature"]
            signed = subset[subset['Lifecycle'] == "✅ Signed & Enacted"]
            dead = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            # 1. ACTIVE (Always Visible)
            draw_categorized_section(active, "Active Bills", "🚀")
            st.markdown("---")
            
            # 2. PASSED SECTION (Always Visible Header)
            st.markdown("### 🎉 Passed Legislation")
            
            # Sub-sections (Always Visible)
            draw_categorized_section(awaiting, "Awaiting Signature", "✍️")
            draw_categorized_section(signed, "Signed & Enacted", "✅")
            st.markdown("---")

            # 3. FAILED (Always Visible)
            draw_categorized_section(dead, "Dead / Failed", "❌")

            # --- MASTER LIST ---
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            
            tab_flat_active = subset[subset['Lifecycle'].isin(["🚀 Active", "✍️ Awaiting Signature", "✅ Signed & Enacted"])]
            tab_flat_failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            tab_flat_active = tab_flat_active.sort_values(by="Bill Number")
            tab_flat_failed = tab_flat_failed.sort_values(by="Bill Number")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🚀 Active / Passed")
                for i, row in tab_flat_active.iterrows():
                    with st.expander(f"{row['Bill Number']} - {row.get('Status')}"):
                        render_bill_card(row)
            with col2:
                st.markdown("#### ❌ Failed / Tabled")
                for i, row in tab_flat_failed.iterrows():
                    with st.expander(f"{row['Bill Number']} - {row.get('Status')}"):
                        render_bill_card(row)
    
    st.sidebar.success("✅ System Online")

else:
    st.info("Add bills to your Google Sheet.")
