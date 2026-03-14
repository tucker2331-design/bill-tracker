import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

st.set_page_config(page_title="Bug Logger Sandbox", layout="wide")
st.title("🧪 Phase 5 Shadow Test: Permanent Bug Logging")
st.info("Testing robust Anti-Duplication logic for writing bugs to the new Google Sheet tab.")

# --- CONFIGURATION ---
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"
MASTERMIND_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"

# --- AUTHENTICATION ---
@st.cache_resource
def get_gspread_client():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Failed to authenticate with Google: {e}")
        return None

def run_bug_scanner():
    gc = get_gspread_client()
    if not gc: return
    
    with st.spinner("Scanning database and checking logs..."):
        try:
            # 1. Download current bills to find active bugs
            df_master = pd.read_csv(MASTERMIND_URL)
            
            # 2. Connect to the new Bug_Logs tab
            sheet = gc.open_by_key(SPREADSHEET_ID)
            bug_worksheet = sheet.worksheet("Bug_Logs")
            existing_logs = bug_worksheet.get_all_records()
            df_logs = pd.DataFrame(existing_logs) if existing_logs else pd.DataFrame(columns=["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"])
            
            # Ensure columns exist in the DataFrame to prevent KeyError if sheet is totally empty
            for col in ["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"]:
                if col not in df_logs.columns:
                    df_logs[col] = ""

            new_bugs_to_log = []
            today_str = datetime.now().strftime("%Y-%m-%d %H:%M")

            # --- BUG DETECTION & ANTI-DUPLICATION LOGIC ---
            
            # A. Find Vocabulary Bugs
            vocab_bugs = df_master[df_master['Lifecycle'].str.contains('⚠️ Unrecognized', na=False)]
            for _, row in vocab_bugs.iterrows():
                bill = str(row['Bill Number'])
                status = str(row['Status'])
                
                # Check for exact Bill + exact Bug Type + currently Open
                is_duplicate = not df_logs[
                    (df_logs['Bill_Number'].astype(str) == bill) & 
                    (df_logs['Bug_Type'] == "Vocabulary") & 
                    (df_logs['Status'] == "🚨 Open")
                ].empty
                
                if not is_duplicate:
                    new_bugs_to_log.append([today_str, bill, "Vocabulary", status, "🚨 Open"])

            # B. Find Routing Bugs
            routing_bugs = df_master[(df_master['Lifecycle'] == '📥 In Committee') & (df_master['Display_Committee'] == 'Unassigned')]
            for _, row in routing_bugs.iterrows():
                bill = str(row['Bill Number'])
                status = str(row['Status'])
                
                is_duplicate = not df_logs[
                    (df_logs['Bill_Number'].astype(str) == bill) & 
                    (df_logs['Bug_Type'] == "Routing") & 
                    (df_logs['Status'] == "🚨 Open")
                ].empty
                
                if not is_duplicate:
                    new_bugs_to_log.append([today_str, bill, "Routing", status, "🚨 Open"])

            # C. Find Sorting Bugs
            sorting_bugs = df_master[df_master['Auto_Folder'] == '📂 Unassigned / General']
            for _, row in sorting_bugs.iterrows():
                bill = str(row['Bill Number'])
                title = str(row['Official Title'])
                
                is_duplicate = not df_logs[
                    (df_logs['Bill_Number'].astype(str) == bill) & 
                    (df_logs['Bug_Type'] == "Sorting") & 
                    (df_logs['Status'] == "🚨 Open")
                ].empty
                
                if not is_duplicate:
                    new_bugs_to_log.append([today_str, bill, "Sorting", title, "🚨 Open"])

            # --- WRITE TO SHEET ---
            if new_bugs_to_log:
                bug_worksheet.append_rows(new_bugs_to_log)
                st.success(f"✅ Successfully appended {len(new_bugs_to_log)} NEW bugs to the permanent log!")
                st.dataframe(pd.DataFrame(new_bugs_to_log, columns=["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"]))
            else:
                st.info("🛡️ Scan complete. 0 new bugs found. (Any existing bugs are already marked '🚨 Open' in the sheet).")
                
        except Exception as e:
            st.error(f"Error during scan: {e}")

# --- UI ---
st.subheader("Step 1: Run the Scanner")
st.write("Click the button below to scan the main database. It will evaluate the Composite Key (Bill + Type + Status) and write any net-new bugs to your `Bug_Logs` tab.")
if st.button("🔍 Run Bug Scanner & Log to Google Sheets", type="primary"):
    run_bug_scanner()

st.divider()

st.subheader("Step 2: Verify Anti-Duplication")
st.write("After the first scan succeeds, check your Google Sheet. Then, **click the button a second time.** It should block all duplicates.")
