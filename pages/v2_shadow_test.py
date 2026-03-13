import streamlit as st
import pandas as pd
import json
import re
import requests
import time

st.set_page_config(page_title="V4 Mastermind UI", layout="wide")
st.title("🧬 Phase 3: The Unified UI (Shadow Test)")
st.info("Testing the dual-view UI: Tracked Bills vs. Full State Backup. Live app.py is untouched.")

# --- URLS ---
MASTERMIND_URL = "https://docs.google.com/spreadsheets/d/1566pCv70iQ7YkTQK71RfYerciK-ukW-QdblTu2-Prfw/gviz/tq?tqx=out:csv&sheet=Sheet1"
MANUAL_TRACKER_URL = "https://docs.google.com/spreadsheets/d/18m752GcvGIPPpqUn_gB0DfA3e4z2UGD0ki0dUZh2Qek/gviz/tq?tqx=out:csv&sheet=Bills"

def clean_bill_id(bill_text):
    if pd.isna(bill_text): return ""
    clean = str(bill_text).upper().replace(" ", "").strip()
    clean = re.sub(r'^([A-Z]+)0+(\d+)$', r'\1\2', clean)
    return clean

@st.cache_data(ttl=60)
def load_databases():
    try:
        # 1. Load Mastermind (All 3600+ Bills)
        df_master = pd.read_csv(MASTERMIND_URL)
        if 'History_Data' in df_master.columns:
            df_master['History_Data'] = df_master['History_Data'].apply(lambda x: json.loads(x) if pd.notna(x) else [])
            df_master['Upcoming_Meetings'] = df_master['Upcoming_Meetings'].apply(lambda x: json.loads(x) if pd.notna(x) else [])

        # 2. Load Manual Tracker (Team Input)
        raw_manual = pd.read_csv(MANUAL_TRACKER_URL)
        raw_manual.columns = raw_manual.columns.str.strip()
        
        # Extract 'Watching' bills
        cols_w = ['Bills Watching', 'Title (Watching)']
        if 'Status (Watching)' in raw_manual.columns: cols_w.append('Status (Watching)')
        df_w = raw_manual[cols_w].copy().dropna(subset=['Bills Watching'])
        df_w.columns = ['Bill Number', 'My Title'] + (['My Status'] if 'Status (Watching)' in raw_manual.columns else [])
        df_w['Type'] = 'Watching'

        # Extract 'Involved' bills
        w_col_name = next((c for c in raw_manual.columns if "Working On" in c and "Title" not in c and "Status" not in c), None)
        df_i = pd.DataFrame()
        if w_col_name:
            cols_i = [w_col_name]
            title_work_col = next((c for c in raw_manual.columns if "Title (Working)" in c), None)
            if title_work_col: cols_i.append(title_work_col)
            status_work_col = next((c for c in raw_manual.columns if "Status (Working)" in c), None)
            if status_work_col: cols_i.append(status_work_col)
            
            df_i = raw_manual[cols_i].copy().dropna(subset=[w_col_name])
            i_new_cols = ['Bill Number']
            if title_work_col: i_new_cols.append('My Title')
            if status_work_col: i_new_cols.append('My Status')
            df_i.columns = i_new_cols
            df_i['Type'] = 'Involved'
        
        # Combine team tracker
        df_team = pd.concat([df_w, df_i], ignore_index=True)
        df_team['Bill Number'] = df_team['Bill Number'].apply(clean_bill_id)
        df_team = df_team.drop_duplicates(subset=['Bill Number'])
        if 'My Title' not in df_team.columns: df_team['My Title'] = "-"
        if 'My Status' not in df_team.columns: df_team['My Status'] = "-"
        df_team['My Title'] = df_team['My Title'].fillna("-")
        df_team['My Status'] = df_team['My Status'].fillna("-")

        # 3. Merge for the Tracked View
        df_tracked = pd.merge(df_team, df_master, on="Bill Number", how="left")
        
        return df_master, df_tracked

    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- FETCH DATA ---
with st.spinner("Downloading and merging state data..."):
    df_master, df_tracked = load_databases()

if not df_master.empty:
    
    # --- UI TOGGLE (TABS) ---
    tab_tracked, tab_master = st.tabs(["🎯 My Tracked Bills", "🏛️ Master State Database (LIS Backup)"])
    
    # TAB 1: Team's Merged View
    with tab_tracked:
        st.subheader("👀 Watching")
        if not df_tracked[df_tracked['Type'] == 'Watching'].empty:
            st.dataframe(df_tracked[df_tracked['Type'] == 'Watching'][['Bill Number', 'My Title', 'Official Title', 'Status', 'Latest_Vote', 'Lifecycle', 'Display_Committee']], use_container_width=True)
        else:
            st.caption("No 'Watching' bills found in your manual sheet.")
            
        st.subheader("🚀 Directly Involved")
        if not df_tracked[df_tracked['Type'] == 'Involved'].empty:
            st.dataframe(df_tracked[df_tracked['Type'] == 'Involved'][['Bill Number', 'My Title', 'Official Title', 'Status', 'Latest_Vote', 'Lifecycle', 'Display_Committee']], use_container_width=True)
        else:
            st.caption("No 'Involved' bills found in your manual sheet.")
            
    # TAB 2: All 3,600+ Bills (QA & Backup)
    with tab_master:
        st.subheader(f"Total Bills Indexed: {len(df_master)}")
        st.markdown("This view acts as an independent backup of the LIS system. Expand a bill below to see its full history.")
        
        # Display the full, unfiltered database
        st.dataframe(
            df_master[['Bill Number', 'Official Title', 'Status', 'Latest_Vote', 'Lifecycle', 'Auto_Folder', 'Current_Committee']], 
            use_container_width=True,
            height=600
        )
        
        st.divider()
        st.subheader("🔍 Deep Dive: Bill History Inspector")
        inspect_bill = st.selectbox("Select a bill to view full history timeline:", df_master['Bill Number'].tolist())
        if inspect_bill:
            bill_row = df_master[df_master['Bill Number'] == inspect_bill].iloc[0]
            st.markdown(f"**{bill_row['Bill Number']}** - {bill_row['Official Title']}")
            if bill_row['History_Data']:
                st.dataframe(pd.DataFrame(bill_row['History_Data']), hide_index=True, use_container_width=True)
            else:
                st.caption("No history found.")

    # --- SIDEBAR: DEVELOPER CONSOLE & SYNC ---
    with st.sidebar:
        st.header("⚙️ Data Controls")
        
        # 1. THE GOD BUTTON
        if st.button("🚀 Sync Latest State Data", type="primary", use_container_width=True):
            GITHUB_OWNER = "tucker2331-design" 
            GITHUB_REPO = "bill-tracker" 
            # Make sure this matches the actual file name of your workflow in the .github/workflows folder!
            WORKFLOW_FILENAME = "backend_worker.yml" 
            
            try:
                GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
            except:
                st.error("Missing GITHUB_TOKEN in Streamlit secrets.")
                st.stop()
                
            url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILENAME}/dispatches"
            headers = {
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            data = {"ref": "main"}
            
            with st.spinner("Waking up Ghost Worker... This takes about 45 seconds."):
                response = requests.post(url, headers=headers, json=data)
                
                if response.status_code == 204:
                    time.sleep(45) 
                    st.cache_data.clear()
                    st.success("✅ Database synced! Page refreshing...")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"Failed to trigger sync: {response.status_code} - {response.text}")
            
        st.divider()
        
        # 2. LOGIC MONITORING
        st.subheader("🚨 Logic Monitoring")
        errors = df_master[df_master['Lifecycle'].str.contains('⚠️ Unrecognized', na=False)]
        
        if not errors.empty:
            st.error(f"Found {len(errors)} unrecognized status(es) in the state database!")
            st.dataframe(errors[['Bill Number', 'Status']], hide_index=True)
        else:
            st.success("Zero logic errors. All 3,600+ bills mapped perfectly.")
