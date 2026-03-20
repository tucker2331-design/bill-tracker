import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="Legislative Calendar", layout="wide")
st.title("📅 Auto-Routing Legislative Calendar")
st.markdown("Fully autonomous calendar powered by the Virginia LIS Auto-Router.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE AUTO-ROUTER (The Master Keys)
# ==========================================
@st.cache_data(ttl=3600) # Check for a new session once an hour
def get_active_session_codes():
    """Dynamically finds the active session and derives both the Azure and API codes."""
    url = "https://lis.virginia.gov/Session/api/getsessionlistasync"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            sessions = res.json()
            
            # SURGERY 1: Validate payload is a list of dictionaries before parsing
            active_session = None
            if isinstance(sessions, list):
                active_session = next((s for s in sessions if isinstance(s, dict) and (s.get('IsActive') or s.get('IsDefault'))), None)
            
            if active_session:
                blob_code = str(active_session['SessionCode'])
                api_code = blob_code[2:] 
                return {
                    "blob": blob_code, 
                    "api": api_code, 
                    "name": active_session.get('DisplayName', f"Session {blob_code}"),
                    "events": active_session.get('SessionEvents', [])
                }
    except Exception as e:
        st.error(f"Auto-Router Failed to connect to Virginia API: {e}")
    
    return {"blob": "20261", "api": "261", "name": "2026 Regular Session", "events": []}

session_context = get_active_session_codes()
SESSION_BLOB = session_context["blob"]
SESSION_API = session_context["api"]

st.sidebar.success(f"📡 **Active Connection:**\n{session_context['name']}")
st.sidebar.caption(f"Azure Key: `{SESSION_BLOB}` | API Key: `{SESSION_API}`")

st.sidebar.header("🎯 Tracked Portfolio")
portfolio_input = st.sidebar.text_area(
    "Enter bills to track (comma separated):", 
    value="HB10, HB863, SB4, HB1204, HB500"
)
TRACKED_BILLS = [b.strip().upper().replace(" ", "") for b in portfolio_input.split(",") if b.strip()]

bypass_filter = st.sidebar.checkbox("⚠️ Bypass Portfolio (Load All Data)", value=False)

TODAY = datetime(2026, 3, 19)
past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE EXTRACTOR (Using the Auto-Routed Keys)
# ==========================================
@st.cache_data(ttl=600)
def fetch_live_data(blob_code, api_code, events):
    data_payload = {"past": pd.DataFrame(), "future": pd.DataFrame(), "schedule": pd.DataFrame(), "session_status": "Active"}
    
    with st.spinner("📥 Extracting Active Data Streams..."):
        try:
            adjourn_event = next((e for e in events if e.get('DisplayName') == "Adjournment"), None)
            if adjourn_event:
                adjourn_date = datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d')
                if TODAY > adjourn_date:
                    data_payload["session_status"] = "Sine Die (Adjourned)"

            sched_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            sched_res = requests.get(sched_url, headers=HEADERS, params={"sessionCode": api_code}, timeout=10)
            if sched_res.status_code == 200:
                sched_data = sched_res.json()
                if isinstance(sched_data, dict) and 'Schedules' in sched_data:
                    data_payload["schedule"] = pd.DataFrame(sched_data['Schedules'])
                else:
                    data_payload["schedule"] = pd.DataFrame(sched_data)

            def safe_fetch_csv(url):
                res = requests.get(url, timeout=10)
                if res.status_code == 200 and "<?xml" not in res.text[:20]:
                    df = pd.read_csv(io.StringIO(res.text))
                    return df.rename(columns=lambda x: x.strip())
                return pd.DataFrame()

            data_payload["past"] = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
            
            if data_payload["session_status"] == "Active":
                data_payload["future"] = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
                
        except Exception as e:
            st.error(f"Extraction Pipeline Warning: {e}")
            
    return data_payload

# ==========================================
# 3. TRANSFORMER (Data Merging & Smart Parsing)
# ==========================================
def process_data(payload, bypass):
    df_past, df_future, df_sched = payload["past"], payload["future"], payload["schedule"]
    processed_events = []

    if not df_past.empty:
        bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
        desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
        
        df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
        
        df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
        mask = (df_past['ParsedDate'] >= pd.to_datetime(past_start)) & (df_past['ParsedDate'] <= pd.to_datetime(TODAY))
        df_past = df_past[mask]
        
        actionable_verbs = ['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign']
        pattern = '|'.join(actionable_verbs)
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]

        if not bypass:
            df_past = df_past[df_past['CleanBill'].isin(TRACKED_BILLS)]
        else:
            df_past = df_past.tail(150)
        
        for _, row in df_past.iterrows():
            outcome_text = str(row[desc_col])
            
            # --- SMART COMMITTEE EXTRACTOR ---
            committee_name = "Floor Action"
            outcome_lower = outcome_text.lower()
            
            if "reported from" in outcome_lower:
                committee_name = outcome_text[outcome_lower.find("reported from") + 13:]
            elif "reported out of" in outcome_lower:
                committee_name = outcome_text[outcome_lower.find("reported out of") + 15:]
            elif "referred to" in outcome_lower:
                committee_name = outcome_text[outcome_lower.find("referred to") + 11:]
            
            committee_name = committee_name.split('(')[0].split(' with ')[0].strip()
            committee_name = committee_name.title() if committee_name else "Floor Action"
            # ----------------------------------

            processed_events.append({
                "Date": row['ParsedDate'].strftime('%Y-%m-%d'), 
                "Time": "Ledger", 
                "Committee": committee_name, 
                "Bill": row['CleanBill'], 
                "Outcome": outcome_text, 
                "AgendaOrder": 0, 
                "IsFuture": False
            })

    if not df_future.empty:
        bill_col = next((c for c in df_future.columns if 'bill' in c.lower()), 'BillNumber')
        date_col = next((c for c in df_future.columns if 'date' in c.lower()), 'DocketDate')
        
        # SURGERY 2: Change 'comm' to 'com' to catch 'ComDes'
        comm_col = next((c for c in df_future.columns if 'com' in c.lower()), None)
        
        seq_col = next((c for c in df_future.columns if 'seq' in c.lower() or 'order' in c.lower()), 'Sequence')
        
        df_future['CleanBill'] = df_future[bill_col].astype(str).str.replace(' ', '').str.upper()
        
        if not bypass:
            df_future = df_future[df_future['CleanBill'].isin(TRACKED_BILLS)]
        else:
            df_future = df_future.head(150)
            
        for _, row in df_future.iterrows():
            processed_events.append({
                "Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'), 
                "Time": "TBD", 
                # Use .get() to prevent hard crashes if column is missing
                "Committee": row.get(comm_col, "Unknown Committee") if comm_col else "Unknown Committee", 
                "Bill": row['CleanBill'], 
                "Outcome": "Pending Hearing", 
                "AgendaOrder": row.get(seq_col, 0), 
                "IsFuture": True
            })

    master_df = pd.DataFrame(processed_events)
    
    if not master_df.empty and not df_sched.empty:
        df_sched['MergeDate'] = pd.to_datetime(df_sched['ScheduleDate']).dt.strftime('%Y-%m-%d')
        master_df['MergeComm'] = master_df['Committee'].str.replace('House ', '').str.replace('Senate ', '')
        df_sched['MergeComm'] = df_sched['OwnerName'].str.replace('House ', '').str.replace('Senate ', '')
        
        merged = pd.merge(master_df, df_sched[['MergeDate', 'MergeComm', 'ScheduleTime']], left_on=['Date', 'MergeComm'], right_on=['MergeDate', 'MergeComm'], how='left')
        merged['Time'] = merged['ScheduleTime'].fillna(master_df['Time'])
        master_df = merged.drop(columns=['MergeDate', 'MergeComm', 'ScheduleTime'])

    return master_df

# ==========================================
# 4. UI RENDERING
# ==========================================
if st.sidebar.button("🚀 Fetch & Render Calendar"):
    raw_payload = fetch_live_data(SESSION_BLOB, SESSION_API, session_context['events'])
    session_state = raw_payload["session_status"]
    
    if session_state == "Sine Die (Adjourned)":
        st.warning(f"🏛️ **Notice:** The {session_context['name']} has adjourned Sine Die. Expect limited future dockets until the next session activates.")
        
    final_df = process_data(raw_payload, bypass_filter)
    
    if final_df.empty:
        st.info("No actionable events found for your portfolio in the current timeframe.")
        st.stop()
        
    final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('Ledger', '11:59 PM').replace('TBD', '11:59 PM'), errors='coerce')

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
