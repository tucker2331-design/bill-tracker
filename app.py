import streamlit as st
import pandas as pd
import requests
import smtplib
from email.mime.text import MIMEText

# --- CONFIGURATION ---
# Your Specific Sheet ID
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"

# API SETUP
API_KEY = st.secrets.get("OPENSTATES_API_KEY")

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- HELPER FUNCTIONS ---
def get_bill_data_batch(bill_numbers):
    """
    Fetches 2026 bill data for a list of bill numbers.
    """
    results = []
    
    # Clean bill numbers (remove spaces, make uppercase)
    clean_bills = [str(b).strip().upper() for b in bill_numbers if str(b).strip()]

    for bill_num in clean_bills:
        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia",
            "session": "2026",  # <--- FORCES 2026 SESSION
            "identifier": bill_num,
            "include": ["actions", "sponsorships"],
            "apikey": API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['results']:
                # Found the bill
                item = data['results'][0]
                latest_action = item['actions'][0]['description'] if item['actions'] else "Introduced"
                latest_date = item['actions'][0]['date'] if item['actions'] else ""
                sponsor = item['sponsorships'][0]['name'] if item['sponsorships'] else "Unknown"
                
                results.append({
                    "Bill Number": bill_num,
                    "Official Title": item['title'], # Renamed for clarity
                    "Status": latest_action,
                    "Date": latest_date,
                    "Sponsor": sponsor,
                    "History": item['actions']
                })
            else:
                # Bill not found
                results.append({
                    "Bill Number": bill_num,
                    "Official Title": "Not found in 2026 Session",
                    "Status": "Unknown",
                    "Date": "-",
                    "Sponsor": "-",
                    "History": []
                })
                
        except Exception as e:
            # API Error
            print(f"Error fetching {bill_num}: {e}")
            
    return pd.DataFrame(results)

def send_notification(email_to, subject, body):
    email_user = st.secrets.get("EMAIL_USER")
    email_pass = st.secrets.get("EMAIL_PASS")
    
    if not email_user or not email_pass:
        st.warning("Cannot send email: Credentials missing in Secrets.")
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
st.title("🏛️ Virginia General Assembly Tracker (2026)")

# 1. LOAD DATA FROM GOOGLE SHEET
try:
    sheet_df = pd.read_csv(SHEET_URL)
    # Clean up column names (remove extra spaces)
    sheet_df.columns = sheet_df.columns.str.strip()
    
    if 'Bill Number' not in sheet_df.columns:
        st.error("Error: Your Google Sheet must have a 'Bill Number' column.")
        st.stop()
        
    # Standardize Bill Numbers in Sheet
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper()
    
    # Handle "Folder" column
    if 'Folder' not in sheet_df.columns:
        sheet_df['Folder'] = "Uncategorized"
    sheet_df['Folder'] = sheet_df['Folder'].fillna("Uncategorized")
    
    # Handle "My Title" column (The new custom category)
    if 'My Title' not in sheet_df.columns:
        # If you haven't added the column yet, we create it temporarily so code doesn't crash
        sheet_df['My Title'] = "-"
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")
    
except Exception as e:
    st.error(f"Could not load Google Sheet. Check permissions. Error: {e}")
    st.stop()

# 2. FETCH REAL DATA AND MERGE
st.write("Fetching latest 2026 data...")
bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    api_df = get_bill_data_batch(bills_to_track)
    
    # MERGE: Combine your Sheet (Folders/My Title) with API (Status/Official Title)
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # Fill in blanks
    final_df['Official Title'] = final_df['Official Title'].fillna("Loading Error")
    
    # 3. SIDEBAR FILTERS
    st.sidebar.header("Filters")
    available_folders = final_df['Folder'].unique()
    selected_folders = st.sidebar.multiselect("Filter by Folder", available_folders)
    
    if selected_folders:
        display_df = final_df[final_df['Folder'].isin(selected_folders)]
    else:
        display_df = final_df

    # 4. DISPLAY DASHBOARD
    st.divider()
    
    st.subheader(f"Tracking {len(display_df)} Bills")
    
    # Sort
    display_df = display_df.sort_values(by=['Folder', 'Bill Number'])
    
    # REORDER COLUMNS: Folder -> Bill -> YOUR TITLE -> Official Title -> Status
    cols_to_show = ['Folder', 'Bill Number', 'My Title', 'Official Title', 'Status', 'Date']
    
    # Show the table
    st.dataframe(
        display_df[cols_to_show],
        use_container_width=True,
        hide_index=True
    )

    # Expanded View
    st.divider()
    st.subheader("🔍 Detailed History")
    
    for i, row in display_df.iterrows():
        # Using YOUR custom title in the expander header if it exists
        display_name = row['My Title'] if row['My Title'] != "-" else row['Official Title']
        
        label = f"{row['Bill Number']} ({row['Folder']}): {display_name}"
        
        with st.expander(label):
            st.markdown(f"**My Summary:** {row['My Title']}")
            st.markdown(f"**Official Title:** {row['Official Title']}")
            st.markdown(f"**Sponsor:** {row['Sponsor']}")
            st.write(f"**Current Status:** {row['Status']} ({row['Date']})")
            
            st.write("**Recent History:**")
            if isinstance(row['History'], list) and len(row['History']) > 0:
                hist_df = pd.DataFrame(row['History'])
                st.table(hist_df[['date', 'description']])
            else:
                st.write("No history available.")

    # 5. NOTIFICATIONS
    st.sidebar.divider()
    if st.sidebar.button("📧 Email Me Update"):
        email_target = st.sidebar.text_input("Confirm Email:")
        if email_target:
            summary = "VA 2026 Bill Tracker Update:\n\n"
            for i, row in final_df.iterrows():
                # Use My Title in email if available
                title_used = row['My Title'] if row['My Title'] != "-" else row['Official Title']
                summary += f"{row['Bill Number']} - {title_used}: {row['Status']} ({row['Date']})\n"
                
            send_notification(email_target, "Bill Tracker Update", summary)
            
else:
    st.warning("Your Google Sheet appears to be empty.")
