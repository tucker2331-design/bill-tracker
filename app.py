import streamlit as st
import pandas as pd
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# --- CONFIGURATION ---
SHEET_ID = "18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Bills"
API_KEY = st.secrets.get("OPENSTATES_API_KEY")

st.set_page_config(page_title="VA Bill Tracker 2026", layout="wide")

# --- FUNCTIONS ---
def get_bill_data_batch(bill_numbers):
    results = []
    # Remove duplicates and clean
    clean_bills = list(set([str(b).strip().upper() for b in bill_numbers if str(b).strip() != 'nan']))

    for bill_num in clean_bills:
        if not bill_num: continue
        
        # We ask for 'subject' to do the auto-sorting
        url = "https://v3.openstates.org/bills"
        params = {
            "jurisdiction": "Virginia",
            "session": "2026",
            "identifier": bill_num,
            "include": ["actions", "sponsorships", "subject"], 
            "apikey": API_KEY
        }
        
        try:
            response = requests.get(url, params=params)
            data = response.json()
            
            if data['results']:
                item = data['results'][0]
                latest_action = item['actions'][0]['description'] if item['actions'] else "Introduced"
                latest_date = item['actions'][0]['date'] if item['actions'] else ""
                
                # AUTO-SORTING LOGIC
                # Grab the first subject tag (e.g., "Education") or use "Uncategorized"
                subjects = item.get('subject', [])
                auto_folder = subjects[0] if subjects else "General / Uncategorized"
                
                results.append({
                    "Bill Number": bill_num,
                    "Official Title": item['title'],
                    "Status": latest_action,
                    "Date": latest_date,
                    "Sponsor": item['sponsorships'][0]['name'] if item['sponsorships'] else "Unknown",
                    "Auto_Folder": auto_folder,
                    "History": item['actions']
                })
            else:
                results.append({
                    "Bill Number": bill_num,
                    "Official Title": "Not found in 2026 Session",
                    "Status": "Unknown",
                    "Date": "-",
                    "Sponsor": "-",
                    "Auto_Folder": "Unknown",
                    "History": []
                })
        except Exception:
            results.append({
                "Bill Number": bill_num,
                "Official Title": "Error Loading",
                "Status": "Error",
                "Date": "-",
                "Sponsor": "-",
                "Auto_Folder": "Error",
                "History": []
            })
            
    return pd.DataFrame(results)

def send_notification(email_to, subject, body):
    email_user = st.secrets.get("EMAIL_USER")
    email_pass = st.secrets.get("EMAIL_PASS")
    
    if not email_user or not email_pass:
        st.error("Email credentials missing.")
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = email_to

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_user, email_pass)
            server.sendmail(email_user, email_to, msg.as_string())
        st.success(f"Alert sent to {email_to}!")
    except Exception as e:
        st.error(f"Failed to send email: {e}")

# --- MAIN APP ---
st.title("🏛️ Virginia General Assembly Tracker")

# 1. LOAD AND PROCESS THE TWO LISTS
try:
    raw_df = pd.read_csv(SHEET_URL)
    
    # Clean Column Names
    raw_df.columns = raw_df.columns.str.strip()
    
    # LIST 1: WATCHING (Columns A & B)
    # We check if these columns exist, then grab data
    if 'Bills Watching' in raw_df.columns:
        df_watching = raw_df[['Bills Watching', 'Title (Watching)']].copy()
        df_watching = df_watching.rename(columns={'Bills Watching': 'Bill Number', 'Title (Watching)': 'My Title'})
        df_watching['Type'] = 'Watching'
    else:
        df_watching = pd.DataFrame()

    # LIST 2: WORKING ON (Columns C & D)
    if 'Bills Working On' in raw_df.columns:
        df_working = raw_df[['Bills Working On', 'Title (Working)']].copy()
        df_working = df_working.rename(columns={'Bills Working On': 'Bill Number', 'Title (Working)': 'My Title'})
        df_working['Type'] = 'Involved'
    else:
        df_working = pd.DataFrame()
        
    # Combine both lists into one master list
    sheet_df = pd.concat([df_watching, df_working], ignore_index=True)
    
    # Cleanup empty rows
    sheet_df = sheet_df.dropna(subset=['Bill Number'])
    sheet_df = sheet_df[sheet_df['Bill Number'].astype(str).str.strip() != '']
    sheet_df['Bill Number'] = sheet_df['Bill Number'].astype(str).str.strip().str.upper()
    sheet_df['My Title'] = sheet_df['My Title'].fillna("-")

except Exception as e:
    st.error(f"Error loading sheet. Please ensure headers are: 'Bills Watching', 'Title (Watching)', 'Bills Working On', 'Title (Working)'. Error: {e}")
    st.stop()

# 2. REFRESH BUTTON
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔄 Refresh & Check Alerts"):
        st.rerun()

# 3. FETCH DATA & MERGE
bills_to_track = sheet_df['Bill Number'].unique().tolist()

if bills_to_track:
    # Get API Data (Including Subjects)
    api_df = get_bill_data_batch(bills_to_track)
    
    # Merge
    final_df = pd.merge(sheet_df, api_df, on="Bill Number", how="left")
    
    # 4. TABS LAYOUT
    tab_involved, tab_watching = st.tabs(["🚀 Directly Involved", "👀 Watching"])

    def draw_bill_list(dataframe):
        if dataframe.empty:
            st.info("No bills in this list.")
            return

        # AUTO-SORT FOLDERS (Using 'Auto_Folder' from API)
        with st.expander("📂 View by Subject (Auto-Sorted)"):
            # Sort subjects alphabetically
            subjects = sorted([s for s in dataframe['Auto_Folder'].unique() if str(s) != 'nan'])
            
            for s in subjects:
                folder_bills = dataframe[dataframe['Auto_Folder'] == s]
                st.write(f"**{s} ({len(folder_bills)})**")
                # Small table for quick view
                st.dataframe(folder_bills[['Bill Number', 'My Title', 'Status']], hide_index=True)

        # MAIN EXPANDED LIST
        st.write("### Detailed List")
        for i, row in dataframe.iterrows():
            # Choose Title: My Title > Official Title
            display_title = row['My Title'] if row['My Title'] != "-" else row['Official Title']
            
            with st.expander(f"{row['Bill Number']}: {display_title} — {row['Status']}"):
                st.markdown(f"**Subject:** {row['Auto_Folder']}")
                st.markdown(f"**Official Title:** {row['Official Title']}")
                st.markdown(f"**Sponsor:** {row['Sponsor']}")
                st.markdown(f"**Last Update:** {row['Date']}")
                st.info(f"**Latest Action:** {row['Status']}")
                
                st.write("**History:**")
                if isinstance(row['History'], list) and len(row['History']) > 0:
                    hist_df = pd.DataFrame(row['History'])
                    st.table(hist_df[['date', 'description']])
                else:
                    st.write("No history available.")

    # DRAW THE TABS
    with tab_involved:
        involved_bills = final_df[final_df['Type'] == 'Involved']
        draw_bill_list(involved_bills)

    with tab_watching:
        watching_bills = final_df[final_df['Type'] == 'Watching']
        draw_bill_list(watching_bills)

    # 5. ALERTS (Bottom Sidebar)
    st.sidebar.header("📢 Email Alerts")
    email_target = st.sidebar.text_input("Recipient Email:")
    
    if st.sidebar.button("Send Report Now"):
        if email_target:
            report = f"VA General Assembly Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
            
            report += "=== DIRECTLY INVOLVED ===\n"
            for i, row in final_df[final_df['Type'] == 'Involved'].iterrows():
                report += f"{row['Bill Number']} ({row['Auto_Folder']}): {row['Status']} [{row['Date']}]\n"
                
            report += "\n=== WATCHING ===\n"
            for i, row in final_df[final_df['Type'] == 'Watching'].iterrows():
                report += f"{row['Bill Number']}: {row['Status']}\n"
                
            send_notification(email_target, "Legislative Update", report)

else:
    st.info("Your list is empty. Add bills to Columns A or C in your Google Sheet.")
