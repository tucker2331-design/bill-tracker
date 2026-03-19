import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Live Data Calendar Test", layout="wide")
st.title("📡 Live-Fire Legislative Calendar")
st.markdown("Pulling real data from Virginia LIS Azure Blob and Schedule API.")

# ==========================================
# 1. CONFIGURATION & PORTFOLIO
# ==========================================
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
SESSION_BLOB = "20261" # The 5-digit code for the Azure CSVs
SESSION_API = "261"    # The shortcode for the Schedule API

# The Lobbyist's Portfolio (Filters the massive CSVs down to what matters)
st.sidebar.header("🎯 Tracked Portfolio")
portfolio_input = st.sidebar.text_area(
    "Enter bills to track (comma separated):", 
    value="HB10, HB863, SB4, HB1204, HB500, HB99"
)
TRACKED_BILLS = [b.strip().upper() for b in portfolio_input.split(",") if b.strip()]

# Time Window
TODAY = datetime(2026, 3, 19) # Hardcoded for testing the specific session end-date
past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE EXTRACTOR (Pulling the Real Data)
# ==========================================
@st.cache_data(ttl=600) # Caches data for 10 mins so we don't spam the state server
def fetch_live_data():
    data_payload = {"past": pd.DataFrame(), "future": pd.DataFrame(), "schedule": pd.DataFrame()}
    
    with st.spinner("📥 Extracting millions of rows from Virginia Azure Blob..."):
        try:
            # A. Fetch Schedule API (For Times and Rooms)
            sched_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            sched_res = requests.get(sched_url, headers=HEADERS, params={"sessionCode": SESSION_API}, timeout=10)
            if sched_res.status_code == 200:
                sched_data = sched_res.json()
                if isinstance(sched_data, dict) and 'Schedules' in sched_data:
                    data_payload["schedule"] = pd.DataFrame(sched_data['Schedules'])
                else:
                    data_payload["schedule"] = pd.DataFrame(sched_data)

            # B. Fetch HISTORY.CSV (For Past Outcomes)
            hist_url = f"https://lis.blob.core.windows.net/lis/{SESSION_BLOB}/HISTORY.CSV"
            hist_res = requests.get(hist_url, timeout=10)
            if hist_res.status_code == 200:
                df_hist = pd.read_csv(io.StringIO(hist_res.text))
                # Standardize column names dynamically in case they change them
                col_map = {c: c for c in df_hist.columns}
                df_hist = df_hist.rename(columns=lambda x: x.strip())
                data_payload["past"] = df_hist
                
            # C. Fetch DOCKET.CSV (For Future Agenda)
            docket_url = f"https://lis.blob.core.windows.net/lis/{SESSION_BLOB}/DOCKET.CSV"
            docket_res = requests.get(docket_url, timeout=10)
            if docket_res.status_code == 200:
                data_payload["future"] = pd.read_csv(io.StringIO(docket_res.text))
                
        except Exception as e:
            st.error(f"Extraction Failed: {e}")
            
    return data_payload

# ==========================================
# 3. THE TRANSFORMER (Cleaning & Merging)
# ==========================================
def process_data(payload):
    df_past = payload["past"]
    df_future = payload["future"]
    df_sched = payload["schedule"]
    
    # If the blobs failed, halt.
    if df_past.empty and df_future.empty:
        return pd.DataFrame()

    processed_events = []

    # --- PROCESS PAST (HISTORY.CSV) ---
    if not df_past.empty:
        # Find the actual column names (LIS is notoriously inconsistent)
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        
        # Filter for portfolio
        df_past = df_past[df_past[bill_col].isin(TRACKED_BILLS)]
        
        # Apply Allowlist Noise Filter
        actionable_verbs = ['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign']
        pattern = '|'.join(actionable_verbs)
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
        
        for _, row in df_past.iterrows():
            processed_events.append({
                "Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'),
                "Time": "TBD", # We will merge this in a second
                "Committee": "Unknown (History)", # History CSV rarely lists the exact committee cleanly
                "Bill": row[bill_col],
                "Outcome": row[desc_col],
                "AgendaOrder": 0,
                "IsFuture": False
            })

    # --- PROCESS FUTURE (DOCKET.CSV) ---
    if not df_future.empty:
        bill_col = next((c for c in df_future.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_future.columns if 'date' in c.lower()), 'DocketDate')
        comm_col = next((c for c in df_future.columns if 'comm' in c.lower()), 'CommitteeName')
        seq_col = next((c for c in df_future.columns if 'seq' in c.lower() or 'order' in c.lower()), 'Sequence')
        
        df_future = df_future[df_future[bill_col].isin(TRACKED_BILLS)]
        
        for _, row in df_future.iterrows():
            processed_events.append({
                "Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'),
                "Time": "TBD",
                "Committee": row[comm_col],
                "Bill": row[bill_col],
                "Outcome": "Pending Hearing",
                "AgendaOrder": row.get(seq_col, 0),
                "IsFuture": True
            })

    master_df = pd.DataFrame(processed_events)
    
    # --- MERGE SCHEDULE TIMES ---
    if not master_df.empty and not df_sched.empty:
        df_sched['MergeDate'] = pd.to_datetime(df_sched['ScheduleDate']).dt.strftime('%Y-%m-%d')
        # Simple alias handling
        master_df['MergeComm'] = master_df['Committee'].str.replace('House ', '').str.replace('Senate ', '')
        df_sched['MergeComm'] = df_sched['OwnerName'].str.replace('House ', '').str.replace('Senate ', '')
        
        # Left join to staple times onto the events
        merged = pd.merge(master_df, df_sched[['MergeDate', 'MergeComm', 'ScheduleTime']], 
                          left_on=['Date', 'MergeComm'], right_on=['MergeDate', 'MergeComm'], how='left')
        
        merged['Time'] = merged['ScheduleTime'].fillna("TBD")
        master_df = merged.drop(columns=['MergeDate', 'MergeComm', 'ScheduleTime'])

    return master_df

# ==========================================
# 4. EXECUTE & RENDER
# ==========================================
if st.sidebar.button("🚀 Fetch & Render Calendar"):
    raw_payload = fetch_live_data()
    final_df = process_data(raw_payload)
    
    if final_df.empty:
        st.warning("No data found for the tracked bills in the selected timeframe.")
        st.stop()
        
    final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('TBD', '11:59 PM'), errors='coerce')

    # THE UI RENDERING ENGINE (Identical to our prototype)
    def render_kanban_week(start_date, end_date, data, is_future_tab=False):
        days = [(start_date + timedelta(days=i)) for i in range(7)]
        cols = st.columns(7)
        
        for i, current_day in enumerate(days):
            date_str = current_day.strftime('%Y-%m-%d')
            with cols[i]:
                st.markdown(f"**{current_day.strftime('%a, %b %d')}**")
                st.markdown("---")
                
                day_events = data[data['Date'] == date_str]
                # Filter by whether it's supposed to be in the past or future tab based on date
                if is_future_tab:
                    day_events = day_events[day_events['IsFuture'] == True]
                else:
                    day_events = day_events[day_events['IsFuture'] == False]
                
                if day_events.empty:
                    st.info("No scheduled meetings.")
                else:
                    day_events = day_events.sort_values(by='DateTime_Sort')
                    for (committee, time_str), group_df in day_events.groupby(['Committee', 'Time'], sort=False):
                        with st.container(border=True):
                            st.markdown(f"🏛️ **{committee}**\n🕰️ *{time_str}*")
                            st.markdown("---")
                            
                            if is_future_tab: group_df = group_df.sort_values(by='AgendaOrder')
                            
                            for _, row in group_df.iterrows():
                                st.markdown(f"**{row['Bill']}**")
                                if is_future_tab:
                                    st.caption(f"📑 *Agenda Item #{int(row['AgendaOrder'])}*")
                                else:
                                    st.caption(f"🔹 *Action:* {row['Outcome']}")
                                st.write("")

    tab_past, tab_future = st.tabs(["⏪ Past Week", "⏩ Future Week"])
    with tab_past: render_kanban_week(past_start, TODAY - timedelta(days=1), final_df, False)
    with tab_future: render_kanban_week(TODAY, future_end, final_df, True)
