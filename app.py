import streamlit as st
import pandas as pd
import requests
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
API_KEY = st.secrets.get("OPENSTATES_API_KEY")

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- CARRIER LIST FOR SMS ---
CARRIERS = {
    "Verizon": "vtext.com",
    "T-Mobile": "tmomail.net",
    "AT&T": "txt.att.net",
    "Sprint": "messaging.sprintpcs.com",
    "Google Fi": "msg.fi.google.com",
}

# --- SMART CATEGORIZATION CONFIG ---
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
        return "✅ Passed & Signed"
    dead_keywords = ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]
    if any(word in status for word in dead_keywords):
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

def send_notification(email_to, phone_num, carrier, subject, body):
    email_user = st.secrets.get("EMAIL_USER")
    email_pass = st.secrets.get("EMAIL_PASS")
    
    if not email_user or not email_pass:
        st.error("Error: EMAIL_USER or EMAIL_PASS missing in Secrets.")
        return

    recipients = []
    if email_to: recipients.append(email_to)
    if phone_num and carrier: 
        clean_phone = "".join(filter(str.isdigit, str(phone_num)))
        if len(clean_phone) == 10:
            recipients.append(f"{clean_phone}@{CARRIERS[carrier]}")

    if not recipients:
        st.warning("No valid email or phone number entered.")
        return

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_user, email_pass)
            for recipient in recipients:
                msg = MIMEText(body)
                msg['Subject'] = subject
                msg['From'] = email_user
                msg['To'] = recipient
                server.sendmail(email_user, recipient, msg.as_string())
        st.success(f"Alerts sent to {len(recipients)} recipients!")
    except Exception as e:
        st.error(f"Failed to send: {e}")

# --- DISPLAY COMPONENT ---
def render_bill_card(row):
    display_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', 'Loading...')
    status = row.get('Status', 'Unknown')
    
    st.markdown(f"**{row['Bill Number']}:** {display_title}")
    st.caption(f"Status: {status} | Last Action: {row.get('Date', '-')}")
    
    history_data = row.get('History')
    if isinstance(history_data, list) and history_data:
        hist_df = pd.DataFrame(history_data)
        if 'date' in hist_df.columns and 'description' in hist_df.columns:
            st.dataframe(hist_df[['date', 'description']], hide_index=True, use_container_width=True)
    st.divider()

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")

try:
    raw_df = pd.read_csv(SHEET_URL)
    raw_df.columns = raw_df.columns.str.strip()
    
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

if st.button("🔄 Refresh Data"):
    st.rerun()

bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    if 'bill_data' not in st.session_state or st.button("Force Server Update"):
        st.session_state['bill_data'] = get_bill_data_batch(bills_to_track)
    
    api_df = st.session_state['bill_data']
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    def draw_categorized_section(bills, title, color_code):
        if bills.empty: return
        st.markdown(f"### {color_code} {title} ({len(bills)})")
        subjects = sorted([s for s in bills['Auto_Folder'].unique() if str(s) != 'nan'])
        for subj in subjects:
            subset = bills[bills['Auto_Folder'] == subj]
            with st.expander(f"📁 {subj} ({len(subset)})", expanded=False):
                for i, row in subset.iterrows():
                    render_bill_card(row)

    st.subheader("🗂️ Categorized View")
    tab_involved, tab_watching = st.tabs(["🚀 Directly Involved", "👀 Watching"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            # 1. CATEGORIZED VIEW
            subset = final_df[final_df['Type'] == b_type]
            
            awaiting = subset[subset['Lifecycle'] == "✍️ Awaiting Signature"]
            passed = subset[subset['Lifecycle'] == "✅ Passed & Signed"]
            active = subset[subset['Lifecycle'] == "🚀 Active"]
            dead = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            draw_categorized_section(awaiting, "Awaiting Signature", "✍️")
            if not awaiting.empty: st.markdown("---")
            draw_categorized_section(active, "Active Bills", "🚀")
            if not active.empty: st.markdown("---")
            draw_categorized_section(passed, "Passed / Signed", "✅")
            if not passed.empty: st.markdown("---")
            draw_categorized_section(dead, "Dead / Failed", "❌")

            # 2. MASTER LIST (Specific to this Tab)
            st.markdown("---")
            st.subheader(f"📜 Master List ({b_type})")
            
            # Filter specifically for this tab
            tab_flat_active = subset[subset['Lifecycle'].isin(["🚀 Active", "✍️ Awaiting Signature", "✅ Passed & Signed"])]
            tab_flat_failed = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            # Numerical Sort
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

    # --- ALERTS SIDEBAR ---
    st.sidebar.header("📢 Alerts")
    email_target = st.sidebar.text_input("Email Address:")
    phone_target = st.sidebar.text_input("Phone Number (10 digits):")
    carrier_target = st.sidebar.selectbox("Select Carrier:", list(CARRIERS.keys()))
    
    if st.sidebar.button("Send Alerts"):
        report = f"VA LEGISLATIVE UPDATE - {datetime.now().strftime('%m/%d')}\n\n"
        for b_type in ["Involved", "Watching"]:
            report += f"=== {b_type.upper()} ===\n"
            rows = final_df[final_df['Type'] == b_type]
            for i, r in rows.iterrows():
                report += f"[{r.get('Auto_Folder','-')}] {r['Bill Number']}: {r.get('Status', 'Unknown')}\n"
            report += "\n"
        send_notification(email_target, phone_target, carrier_target, "Bill Tracker Update", report)
else:
    st.info("Add bills to your Google Sheet.")
