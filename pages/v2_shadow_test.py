import streamlit as st
import pandas as pd
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

st.set_page_config(page_title="Phase 6 Sandbox", layout="wide")
st.title("🧪 Phase 6: The Sniffer & The Watchman")
st.info("Testing the Auto-Session Sniffer and the decoupled Sync Failure logging.")

# --- CONFIGURATION ---
SPREADSHEET_ID = "1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw"
GITHUB_OWNER = "tucker2331-design"
GITHUB_REPO = "bill-tracker"
WORKFLOW_FILENAME = "backend_worker.yml"

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

# --- FEATURE 1: AUTO-SESSION SNIFFER ---
def test_session_sniffer():
    with st.spinner("Pinging Virginia LIS servers to find active session..."):
        now = datetime.now()
        year = now.year
        # If we are in Nov/Dec, check next year's pre-filing folders first
        years_to_check = [year + 1, year] if now.month >= 11 else [year]
        
        log = []
        found_session = None
        
        for y in years_to_check:
            # Look for Special Session 3, then 2, then 1, then Regular (1)
            for suffix in ["3", "2", "1"]:
                session_code = f"{y}{suffix}"
                test_url = f"https://lis.blob.core.windows.net/lisfiles/{session_code}/HISTORY.CSV"
                
                try:
                    response = requests.head(test_url, timeout=3)
                    if response.status_code == 200:
                        log.append(f"🟢 SUCCESS: Found live data at {session_code}")
                        found_session = session_code
                        break # Stop looking once we find the most recent one
                    else:
                        log.append(f"🔴 Miss: {session_code} does not exist yet (Error {response.status_code})")
                except requests.exceptions.RequestException as e:
                    log.append(f"⚠️ Error checking {session_code}: {e}")
            
            if found_session:
                break
                
        # Fallback if the state servers are completely down
        if not found_session:
            found_session = f"{year}1"
            log.append(f"⚠️ FALLBACK TRIGGERED: Defaulting to {found_session}")
            
        return found_session, log

st.subheader("Step 1: Test the Auto-Session Sniffer")
st.write("Click below to force the code to dynamically figure out the API code without hardcoding.")
if st.button("🐕 Sniff for Active Session", type="primary"):
    active_session, sniffer_log = test_session_sniffer()
    
    st.success(f"**Target Locked:** The engine will automatically use API Code ` {active_session} `")
    
    with st.expander("View Server Ping Log"):
        for entry in sniffer_log:
            st.write(entry)

st.divider()

# --- FEATURE 2: THE WATCHMAN (SYNC FAILURE LOGGING) ---
def run_watchman():
    gc = get_gspread_client()
    if not gc: return
    
    try:
        GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    except:
        st.error("Missing GITHUB_TOKEN in secrets.")
        return

    with st.spinner("Checking GitHub logs for crashes..."):
        # 1. Ask GitHub for recent failures
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        fail_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILENAME}/runs?status=failure&per_page=5"
        
        try:
            r_fail = requests.get(fail_url, headers=headers)
            if r_fail.status_code != 200:
                st.error("Failed to reach GitHub API.")
                return
                
            runs = r_fail.json().get('workflow_runs', [])
            if not runs:
                st.info("✅ GitHub is healthy! No recent failures found to log.")
                return
                
            # 2. Connect to the Google Sheet
            sheet = gc.open_by_key(SPREADSHEET_ID)
            bug_worksheet = sheet.worksheet("Bug_Logs")
            existing_logs = bug_worksheet.get_all_records()
            df_logs = pd.DataFrame(existing_logs) if existing_logs else pd.DataFrame(columns=["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"])
            for col in ["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"]:
                if col not in df_logs.columns: df_logs[col] = ""

            new_bugs_to_log = []
            
            # 3. Process failures and check for duplicates
            for run in runs:
                raw_time = run['updated_at']
                dt = datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%SZ") - timedelta(hours=4)
                time_str = dt.strftime("%Y-%m-%d %H:%M")
                run_id = str(run['id'])
                details = f"GitHub Run ID: {run_id}"
                
                # Anti-Duplication: Did we already log this exact GitHub Run ID?
                is_duplicate = not df_logs[
                    (df_logs['Bug_Type'] == "🔌 Background Sync Failure") & 
                    (df_logs['Details'].str.contains(run_id, na=False))
                ].empty
                
                if not is_duplicate:
                    new_bugs_to_log.append([time_str, "SYSTEM", "🔌 Background Sync Failure", details, "🚨 Open"])

            # 4. Write to Sheet
            if new_bugs_to_log:
                bug_worksheet.append_rows(new_bugs_to_log)
                st.error(f"⚠️ The Watchman caught {len(new_bugs_to_log)} unlogged sync failures and wrote them to the Google Sheet!")
                st.dataframe(pd.DataFrame(new_bugs_to_log, columns=["Date_Found", "Bill_Number", "Bug_Type", "Details", "Status"]))
            else:
                st.info("🛡️ The Watchman found failures on GitHub, but they are already logged in your sheet. No duplicates added.")

        except Exception as e:
            st.error(f"Watchman Error: {e}")

st.subheader("Step 2: Test the Watchman")
st.write("Streamlit will ask GitHub if the backend crashed. If it did, Streamlit will write the crash to your `Bug_Logs` tab.")
if st.button("👀 Run Watchman (Check GitHub)", type="primary"):
    run_watchman()
