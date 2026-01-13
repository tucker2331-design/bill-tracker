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
    "Virgin Mobile": "vmobl.com",
    "Boost Mobile": "sms.myboostmobile.com",
    "Cricket": "sms.cricketwireless.net",
    "US Cellular": "email.uscc.net"
}

# --- HELPER FUNCTIONS ---

def determine_lifecycle(status_text):
    """Sorts bills into Active, Passed, or Dead based on official text."""
    status = str(status_text).lower()
    
    # 1. PASSED & SIGNED (Success)
    if "signed by governor" in status or "enacted" in status or "approved by governor" in status or "chapter" in status:
        return "✅ Passed & Signed"
    
    # 2. DEAD / FAILED / TABLED (Irrelevant)
    dead_keywords = ["tabled", "failed", "stricken", "passed by indefinitely", "left in", "defeated", "no action taken", "incorporated into"]
    if any(word in status for word in dead_keywords):
        return "❌ Dead / Tabled"
        
    # 3. ACTIVE (Default)
    return "🚀 Active"

def get_bill_data_batch(bill_numbers):
    results = []
    # Clean up bill numbers (Remove empty rows)
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))
    total = len(clean_bills)
    
    # Progress Bar
    progress_bar = st.progress(0, text="Connecting to VA Legislature...")

    for i, bill_num in enumerate(clean_bills):
        if not bill_num: continue
        
        # Safety Pause (Prevents 429 Errors)
        time.sleep(1.2)
        progress_bar.progress((i + 1) / total, text=f"Checking {bill_num}...")

        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia",
            "session": "2026",
            "identifier": bill_num,
            "include": ["actions", "sponsorships", "abstracts"], 
            "apikey": API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            
            # HANDLE ERRORS
            if response.status_code == 429:
                results.append({"Bill Number": bill_num, "Status": "Rate Limited", "Auto_Folder": "System Alert", "Lifecycle": "Unknown"})
                break
            
            if response.status_code != 200:
                results.append({"Bill Number": bill_num, "Status": "Error", "Auto_Folder": "System Alert", "Lifecycle": "Unknown"})
                continue

            data = response.json()
            if data['results']:
                item = data['results'][0]
                latest_action = item['actions'][0]['description'] if item['actions'] else "Introduced"
                latest_date = item['actions'][0]['date'] if item['actions'] else ""
                
                # CHECK FOR GOVERNOR STATUS
                gov_status = ""
                if "Governor" in latest_action:
                    gov_status = f" | GOV: {latest_action}"

                # --- PURE GOVERNMENT SORTING ---
                # We check the official 'subject' list from the API.
                # If the government assigned a subject, we use it.
                # If the government left it blank, we label it "Unassigned".
                subjects = item.get('subject', [])
                if subjects:
                    # Use the first subject tag provided by the state
                    auto_folder = subjects[0]
                else:
                    auto_folder = "Unassigned"

                results.append({
                    "Bill Number": bill_num,
                    "Official Title": item['title'],
                    "Status": latest_action + gov_status,
                    "Date": latest_date,
                    "Sponsor": item['sponsorships'][0]['name'] if item['sponsorships'] else "Unknown",
                    "Auto_Folder": auto_folder,
                    "History": item['actions'],
                    "Lifecycle": determine_lifecycle(latest_action)
                })
            else:
                results.append({"Bill Number": bill_num, "Official Title": "Not Found", "Auto_Folder": "Unassigned", "Lifecycle": "Unknown"})
                
        except Exception:
            results.append({"Bill Number": bill_num, "Status": "Error", "Auto_Folder": "Error", "Lifecycle": "Unknown"})
            
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
    
    # Phone to Email Gateway Logic
    if phone_num and carrier: 
        clean_phone = "".join(filter(str.isdigit, str(phone_num)))
        if len(clean_phone) == 10:
            sms_email = f"{clean_phone}@{CARRIERS[carrier]}"
            recipients.append(sms_email)
        else:
            st.warning("Phone number must be 10 digits.")

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

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")

# 1. LOAD DATA
try:
    raw_df = pd.read_csv(SHEET_URL)
    raw_df.columns = raw_df.columns.str.strip()
    
    # Load "Watching" List
    if 'Bills Watching' in raw_df.columns:
        df_w = raw_df[['Bills Watching', 'Title (Watching)']].copy()
        df_w.columns = ['Bill Number', 'My Title']
        df_w['Type'] = 'Watching'
    else: df_w = pd.DataFrame()

    # Load "Working On" List
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

# 2. REFRESH BUTTON
if st.button("🔄 Refresh Data"):
    st.rerun()

# 3. FETCH & DISPLAY
bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    # Session state prevents re-downloading on every click
    if 'bill_data' not in st.session_state or st.button("Force Server Update"):
        st.session_state['bill_data'] = get_bill_data_batch(bills_to_track)
    
    api_df = st.session_state['bill_data']
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # --- DISPLAY FUNCTION ---
    def draw_section(bills, title):
        if bills.empty: return
        st.subheader(f"{title} ({len(bills)})")
        
        # 1. Get all unique Official Subjects in this list
        subjects = bills['Auto_Folder'].unique()
        # 2. Sort subjects alphabetically
        subjects = sorted([s for s in subjects if str(s) != 'nan'])
        
        # 3. Create a Folder for each Subject
        for subj in subjects:
            subset = bills[bills['Auto_Folder'] == subj]
            with st.expander(f"📂 {subj} ({len(subset)})"):
                for i, row in subset.iterrows():
                    display_title = row['My Title'] if row['My Title'] != "-" else row.get('Official Title', 'Loading...')
                    status = row.get('Status', 'Unknown')
                    
                    st.markdown(f"**{row['Bill Number']}:** {display_title}")
                    st.caption(f"Status: {status} | Date: {row.get('Date', '-')}")
                    
                    if isinstance(row.get('History'), list):
                         st.table(pd.DataFrame(row['History'])[['date', 'description']])
                    st.divider()

    # --- TABS ---
    tab_involved, tab_watching = st.tabs(["🚀 Directly Involved", "👀 Watching"])

    for tab, b_type in [(tab_involved, "Involved"), (tab_watching, "Watching")]:
        with tab:
            subset = final_df[final_df['Type'] == b_type]
            
            # SPLIT INTO 3 SECTIONS (Smart Lifecycle)
            active = subset[subset['Lifecycle'] == "🚀 Active"]
            passed = subset[subset['Lifecycle'] == "✅ Passed & Signed"]
            dead = subset[subset['Lifecycle'] == "❌ Dead / Tabled"]
            
            draw_section(active, "🚀 Active Bills")
            if not passed.empty:
                st.markdown("---")
                draw_section(passed, "✅ Passed / Signed")
            if not dead.empty:
                st.markdown("---")
                draw_section(dead, "❌ Dead / Tabled / Failed")

    # --- ALERTS SIDEBAR ---
    st.sidebar.header("📢 Alerts")
    email_target = st.sidebar.text_input("Email Address:")
    
    # Phone Input
    phone_target = st.sidebar.text_input("Phone Number (10 digits):")
    carrier_target = st.sidebar.selectbox("Select Carrier:", list(CARRIERS.keys()))
    
    if st.sidebar.button("Send Alerts"):
        report = f"VA LEGISLATIVE UPDATE - {datetime.now().strftime('%m/%d')}\n\n"
        
        # Build Report
        for b_type in ["Involved", "Watching"]:
            report += f"=== {b_type.upper()} ===\n"
            rows = final_df[final_df['Type'] == b_type]
            for i, r in rows.iterrows():
                report += f"[{r.get('Auto_Folder','-')}] {r['Bill Number']}: {r.get('Status', 'Unknown')}\n"
            report += "\n"

        send_notification(email_target, phone_target, carrier_target, "Bill Tracker Update", report)

else:
    st.info("Add bills to your Google Sheet.")
