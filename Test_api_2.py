import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Season-Aware Calendar", layout="wide")
st.title("📡 Live-Fire Legislative Calendar")
st.markdown("Season-aware tracking using the Virginia LIS Session API & Azure Blobs.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# Sidebar Settings
st.sidebar.header("⚙️ System Config")
SESSION_BLOB = st.sidebar.text_input("Azure Blob Session Code:", value="261") # Changed default to 261 to avoid tokenizing error
SESSION_API = st.sidebar.text_input("API Session Code:", value="261")

st.sidebar.header("🎯 Tracked Portfolio")
portfolio_input = st.sidebar.text_area(
    "Enter bills to track (comma separated):", 
    value="HB10, HB863, SB4, HB1204, HB500"
)
TRACKED_BILLS = [b.strip().upper() for b in portfolio_input.split(",") if b.strip()]

TODAY = datetime(2026, 3, 19)
past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 1. EXTRACTOR: Season-Aware Data Pull
# ==========================================
@st.cache_data(ttl=600)
def fetch_live_data(blob_code, api_code):
    data_payload = {"past": pd.DataFrame(), "future": pd.DataFrame(), "schedule": pd.DataFrame(), "session_status": "Active"}
    
    with st.spinner("📥 Checking Session Status & Extracting Data..."):
        try:
            # A. Ping Session API to check if we are in Off-Season
            session_url = "https://lis.virginia.gov/Session/api/getsessionlistasync"
            session_res = requests.get(session_url, headers=HEADERS, timeout=5)
            if session_res.status_code == 200:
                sessions = session_res.json()
                # Find the current session (Looking for 20261)
                current_session = next((s for s in sessions if str(s.get('SessionCode')) == "20261"), None)
                if current_session and 'SessionEvents' in current_session:
                    events = current_session['SessionEvents']
                    adjourn_event = next((e for e in events if e.get('DisplayName') == "Adjournment"), None)
                    if adjourn_event:
                        adjourn_date = datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d')
                        if TODAY > adjourn_date:
                            data_payload["session_status"] = "Sine Die (Adjourned)"

            # B. Fetch Schedule API
            sched_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            sched_res = requests.get(sched_url, headers=HEADERS, params={"sessionCode": api_code}, timeout=10)
            if sched_res.status_code == 200:
                sched_data = sched_res.json()
                if isinstance(sched_data, dict) and 'Schedules' in sched_data:
                    data_payload["schedule"] = pd.DataFrame(sched_data['Schedules'])
                else:
                    data_payload["schedule"] = pd.DataFrame(sched_data)

            # C. Safe CSV Fetcher (Prevents the XML Tokenizing Crash)
            def safe_fetch_csv(url):
                res = requests.get(url, timeout=10)
                if res.status_code == 200 and "<?xml" not in res.text[:20]: # Check for Azure XML error trap
                    df = pd.read_csv(io.StringIO(res.text))
                    return df.rename(columns=lambda x: x.strip())
                return pd.DataFrame()

            data_payload["past"] = safe_fetch_csv(f"https://lis.blob.core.windows.net/lis/{blob_code}/HISTORY.CSV")
            
            # Only pull docket if we are actively in session (saves bandwidth and prevents errors)
            if data_payload["session_status"] == "Active":
                data_payload["future"] = safe_fetch_csv(f"https://lis.blob.core.windows.net/lis/{blob_code}/DOCKET.CSV")
                
        except Exception as e:
            st.error(f"Extraction Pipeline Warning: {e}")
            
    return data_payload

# ==========================================
# 2. TRANSFORMER (Data Merging)
# ==========================================
def process_data(payload):
    df_past, df_future, df_sched = payload["past"], payload["future"], payload["schedule"]
    processed_events = []

    if not df_past.empty:
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        
        df_past = df_past[df_past[bill_col].isin(TRACKED_BILLS)]
        actionable_verbs = ['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign']
        pattern = '|'.join(actionable_verbs)
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
        
        for _, row in df_past.iterrows():
            processed_events.append({"Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'), "Time": "TBD", "Committee": "Floor/Unknown", "Bill": row[bill_col], "Outcome": row[desc_col], "AgendaOrder": 0, "IsFuture": False})

    if not df_future.empty:
        bill_col = next((c for c in df_future.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_future.columns if 'date' in c.lower()), 'DocketDate')
        comm_col = next((c for c in df_future.columns if 'comm' in c.lower()), 'CommitteeName')
        seq_col = next((c for c in df_future.columns if 'seq' in c.lower() or 'order' in c.lower()), 'Sequence')
        
        df_future = df_future[df_future[bill_col].isin(TRACKED_BILLS)]
        for _, row in df_future.iterrows():
            processed_events.append({"Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'), "Time": "TBD", "Committee": row[comm_col], "Bill": row[bill_col], "Outcome": "Pending Hearing", "AgendaOrder": row.get(seq_col, 0), "IsFuture": True})

    master_df = pd.DataFrame(processed_events)
    
    if not master_df.empty and not df_sched.empty:
        df_sched['MergeDate'] = pd.to_datetime(df_sched['ScheduleDate']).dt.strftime('%Y-%m-%d')
        master_df['MergeComm'] = master_df['Committee'].str.replace('House ', '').str.replace('Senate ', '')
        df_sched['MergeComm'] = df_sched['OwnerName'].str.replace('House ', '').str.replace('Senate ', '')
        
        merged = pd.merge(master_df, df_sched[['MergeDate', 'MergeComm', 'ScheduleTime']], left_on=['Date', 'MergeComm'], right_on=['MergeDate', 'MergeComm'], how='left')
        merged['Time'] = merged['ScheduleTime'].fillna("TBD")
        master_df = merged.drop(columns=['MergeDate', 'MergeComm', 'ScheduleTime'])

    return master_df

# ==========================================
# 3. UI RENDERING
# ==========================================
if st.sidebar.button("🚀 Fetch & Render Calendar"):
    raw_payload = fetch_live_data(SESSION_BLOB, SESSION_API)
    session_state = raw_payload["session_status"]
    
    if session_state == "Sine Die (Adjourned)":
        st.warning("🏛️ **Notice:** The General Assembly has adjourned Sine Die. Expect limited future dockets until Veto Session.")
        
    final_df = process_data(raw_payload)
    
    if final_df.empty:
        st.info("No actionable events found for your portfolio in the current data.")
        st.stop()
        
    final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('TBD', '11:59 PM'), errors='coerce')

    def render_kanban_week(start_date, end_date, data, is_future_tab=False):
        days = [(start_date + timedelta(days=i)) for i in range(7)]
        cols = st.columns(7)
        
        for i, current_day in enumerate(days):
            date_str = current_day.strftime('%Y-%m-%d')
            with cols[i]:
                st.markdown(f"**{current_day.strftime('%a, %b %d')}**")
                st.markdown("---")
                
                day_events = data[data['Date'] == date_str]
                day_events = day_events[day_events['IsFuture'] == is_future_tab]
                
                if day_events.empty:
                    if is_future_tab and session_state != "Active":
                        st.caption("Off-Season")
                    else:
                        st.info("No meetings.")
                else:
                    day_events = day_events.sort_values(by='DateTime_Sort')
                    for (committee, time_str), group_df in day_events.groupby(['Committee', 'Time'], sort=False):
                        with st.container(border=True):
                            st.markdown(f"🏛️ **{committee}**\n🕰️ *{time_str}*")
                            st.markdown("---")
                            if is_future_tab: group_df = group_df.sort_values(by='AgendaOrder')
                            for _, row in group_df.iterrows():
                                st.markdown(f"**{row['Bill']}**")
                                if is_future_tab: st.caption(f"📑 *Item #{int(row['AgendaOrder'])}*")
                                else: st.caption(f"🔹 *{row['Outcome']}*")

    tab_past, tab_future = st.tabs(["⏪ Past Week", "⏩ Future Week"])
    with tab_past: render_kanban_week(past_start, TODAY - timedelta(days=1), final_df, False)
    with tab_future: render_kanban_week(TODAY, future_end, final_df, True)
