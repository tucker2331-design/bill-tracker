import streamlit as st
import pandas as pd
import requests
import smtplib
from email.mime.text import MIMEText

# --- CONFIGURATION ---
# REPLACE THE ID BELOW WITH YOUR GOOGLE SHEET ID
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"

# API SETUP
API_KEY = st.secrets.get("OPENSTATES_API_KEY", "YOUR_API_KEY_HERE")

st.set_page_config(page_title="VA Bill Tracker", layout="wide")

# --- HELPER FUNCTIONS ---
def get_bill_data(bill_identifier):
    """Fetch bill details from Open States API."""
    # Using the standard V3 API endpoint
    url = "https://v3.openstates.org/bills"
    params = {
        "jurisdiction": "Virginia",
        "identifier": bill_identifier,
        "include": ["abstracts", "actions", "sponsorships"],
        "apikey": API_KEY
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            results = response.json().get('results', [])
            if results:
                return results[0]
    except Exception as e:
        return None
    return None

def send_notification(email_to, subject, body):
    email_user = st.secrets.get("EMAIL_USER")
    email_pass = st.secrets.get("EMAIL_PASS")
    
    if not email_user or not email_pass:
        st.error("Email credentials not configured in Secrets!")
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = email_to

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_to, msg.as_string())
        st.success(f"Notification sent to {email_to}!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# --- APP LAYOUT ---
st.title("🏛️ Virginia General Assembly Tracker")

# 1. LOAD DATA FROM GOOGLE SHEET
try:
    df_tracking = pd.read_csv(SHEET_URL)
    # Basic cleaning to handle potential empty rows or bad data
    df_tracking = df_tracking.dropna(how='all')
    
    # Check if 'Bill Number' column exists
    if 'Bill Number' not in df_tracking.columns:
        st.error("Error: Your Google Sheet must have a column named 'Bill Number' in Row 1.")
        st.stop()
except Exception as e:
    st.error(f"Could not load Google Sheet. Make sure it is 'Public to anyone with link'. Error: {e}")
    st.stop()

# Sidebar: Filtering
st.sidebar.header("Filter & Sort")
all_folders = df_tracking['Folder'].unique().tolist() if 'Folder' in df_tracking.columns else []
selected_folder = st.sidebar.multiselect("Filter by Folder", all_folders)

if selected_folder:
    bills_to_show = df_tracking[df_tracking['Folder'].isin(selected_folder)]
else:
    bills_to_show = df_tracking

# 2. FETCH LATEST DATA
if not bills_to_show.empty:
    bill_data_list = []
    
    st.write(f"Tracking **{len(bills_to_show)}** bills...")
    my_bar = st.progress(0)
    
    for index, row in bills_to_show.iterrows():
        bill_num = row['Bill Number']
        # Skip empty bill numbers
        if pd.isna(bill_num) or str(bill_num).strip() == "":
            continue
            
        data = get_bill_data(str(bill_num).strip())
        
        if data:
            latest_action = data['actions'][0]['description'] if data['actions'] else "No actions yet"
            latest_date = data['actions'][0]['date'] if data['actions'] else ""
            sponsor = data['sponsorships'][0]['name'] if data['sponsorships'] else "Unknown"
            title = data['title']
            
            bill_data_list.append({
                "Bill": data['identifier'],
                "Title": title,
                "Sponsor": sponsor,
                "Folder": row.get('Folder', 'Uncategorized'),
                "Last Action": latest_action,
                "Date": latest_date,
                "History": data['actions']
            })
        else:
            # Handle cases where bill isn't found (maybe a typo in the sheet)
            bill_data_list.append({
                "Bill": bill_num,
                "Title": "Not Found (Check Typos)",
                "Sponsor": "-",
                "Folder": row.get('Folder', 'Uncategorized'),
                "Last Action": "Error loading",
                "Date": "-",
                "History": []
            })
            
        my_bar.progress((index + 1) / len(bills_to_show))
        
    df_results = pd.DataFrame(bill_data_list)

    # 3. DASHBOARD VIEW
    st.divider()
    
    # SIMPLE VIEW
    st.subheader("📋 Simplified View")
    if not df_results.empty:
        st.dataframe(df_results[['Bill', 'Folder', 'Last Action', 'Date', 'Sponsor']], use_container_width=True)

        # EXPANDED VIEW
        st.subheader("🔍 Expanded View & History")
        for i, row in df_results.iterrows():
            with st.expander(f"{row['Bill']}: {row['Title']} ({row['Last Action']})"):
                st.write(f"**Sponsor:** {row['Sponsor']}")
                st.write(f"**Folder:** {row['Folder']}")
                st.write("**Full History:**")
                
                history_df = pd.DataFrame(row['History'])
                if not history_df.empty:
                    st.table(history_df[['date', 'description']])
                else:
                    st.write("No history available.")
                    
        # 4. NOTIFICATIONS
        st.sidebar.divider()
        st.sidebar.header("🔔 Notifications")
        email_target = st.sidebar.text_input("Enter Email for Update")
        
        if st.sidebar.button("Check for Updates & Notify"):
            summary_text = "Virginia Bill Tracker Update:\n\n"
            for i, row in df_results.iterrows():
                summary_text += f"{row['Bill']}: {row['Last Action']} ({row['Date']})\n"
                
            send_notification(email_target, "VA Bill Tracker Update", summary_text)
    else:
        st.warning("No data found for these bills.")

else:
    st.info("No bills found in your Google Sheet! Add rows to the 'Bills' tab.")
