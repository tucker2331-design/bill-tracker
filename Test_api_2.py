import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar", layout="wide")
st.title("📅 Auto-Routing Legislative Calendar")
st.markdown("Fully autonomous calendar powered by the Virginia LIS Auto-Router.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE AUTO-ROUTER (Enterprise Time-Based)
# ==========================================
@st.cache_data(ttl=3600)
def get_active_session_codes(merge_upcoming=False):
    """Dynamically routes sessions based on actual Convene/Adjourn timestamps."""
    url = "https://lis.virginia.gov/Session/api/getsessionlistasync"
    active_sessions = []
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            sessions = res.json()
            if isinstance(sessions, list):
                
                default_session = next((s for s in sessions if isinstance(s, dict) and s.get('IsDefault')), None)
                
                if default_session:
                    active_sessions.append(default_session)
                    
                    if merge_upcoming:
                        current_date = datetime.now()
                        current_year = current_date.year
                        
                        for s in sessions:
                            raw_code = str(s.get('SessionCode', ''))
                            
                            # Fast string check: instantly skip anything older than 1 year
                            if len(raw_code) >= 4 and raw_code[:4].isdigit():
                                if int(raw_code[:4]) < (current_year - 1):
                                    continue
                            
                            if raw_code == str(default_session.get('SessionCode')):
                                continue
                                
                            events = s.get('SessionEvents', [])
                            convene_event = next((e for e in events if e.get('DisplayName') == "Convene"), None)
                            adjourn_event = next((e for e in events if e.get('DisplayName') == "Adjournment"), None)
                            
                            if convene_event:
                                try:
                                    convene_date = datetime.strptime(convene_event['ActualDate'][:10], '%Y-%m-%d')
                                    
                                    if adjourn_event:
                                        adjourn_date = datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d')
                                        if current_date <= adjourn_date + timedelta(days=1):
                                            active_sessions.append(s)
                                    else:
                                        if convene_date.year >= current_year:
                                            active_sessions.append(s)
                                except:
                                    pass

                else:
                    active_sessions = [s for s in sessions if isinstance(s, dict) and s.get('IsActive')]

    except Exception as e:
        st.error(f"Auto-Router Failed: {e}")

    formatted_sessions = []
    for s in active_sessions:
        blob_code = str(s['SessionCode'])
        display_name = s.get('DisplayName', f"Session {blob_code}")
        is_special = "Special" in display_name or s.get('IsDefault') is False
        
        formatted_sessions.append({
            "blob": blob_code, 
            "api": blob_code[2:], 
            "name": display_name,
            "events": s.get('SessionEvents', []),
            "is_special": is_special
        })

    if not formatted_sessions:
        current_year = str(datetime.now().year)
        formatted_sessions = [{"blob": f"{current_year}1", "api": f"{current_year[2:]}1", "name": f"{current_year} Regular Session", "events": [], "is_special": False}]

    return formatted_sessions

# --- UI Toggles for Sidebar ---
st.sidebar.header("⚙️ System Controls")
merge_sessions_toggle = st.sidebar.toggle("🌉 Merge Upcoming Transition Sessions", value=False, help="Enable this during the window between a Regular Session ending and a Special Session beginning to view both calendars simultaneously.")

session_context_list = get_active_session_codes(merge_upcoming=merge_sessions_toggle)

# Hardcoded for test environment viewing
bypass_filter = True 
TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

TODAY = datetime(2026, 3, 20)
past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE EXTRACTOR (Multi-Stream)
# ==========================================
@st.cache_data(ttl=600)
def fetch_live_data(sessions):
    master_payload = {
        "past": pd.DataFrame(), 
        "future": pd.DataFrame(), 
        "schedule": pd.DataFrame(), 
        "status_flags": []
    }
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200 and "<?xml" not in res.text[:20]:
                df = pd.read_csv(io.StringIO(res.text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner(f"📥 Extracting Data Streams from {len(sessions)} session(s)..."):
        for session in sessions:
            blob_code, api_code = session["blob"], session["api"]
            
            # 1. Schedule API
            sched_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            try:
                sched_res = requests.get(sched_url, headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
                if sched_res.status_code == 200:
                    sched_data = sched_res.json()
                    new_sched = pd.DataFrame(sched_data.get('Schedules', sched_data))
                    if not new_sched.empty:
                        master_payload["schedule"] = pd.concat([master_payload["schedule"], new_sched] if not master_payload["schedule"].empty else [new_sched], ignore_index=True)
            except: pass

            # 2. History CSV
            new_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
            if not new_past.empty:
                new_past['Is_Special'] = session['is_special']
                master_payload["past"] = pd.concat([master_payload["past"], new_past] if not master_payload["past"].empty else [new_past], ignore_index=True)

            # 3. Check for Adjournment
            is_sine_die = False
            adjourn_event = next((e for e in session.get('events', []) if e.get('DisplayName') == "Adjournment"), None)
            if adjourn_event:
                if TODAY > datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d'):
                    is_sine_die = True
                    master_payload["status_flags"].append(f"{session['name']} adjourned Sine Die.")

            # 4. Docket CSV
            if not is_sine_die:
                new_future = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/DOCKET.CSV")
                if not new_future.empty:
                    new_future['Is_Special'] = session['is_special']
                    master_payload["future"] = pd.concat([master_payload["future"], new_future] if not master_payload["future"].empty else [new_future], ignore_index=True)

    return master_payload

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
        
        if 'Is_Special' in df_past.columns:
            df_past.loc[df_past['Is_Special'] == True, 'CleanBill'] = df_past['CleanBill'] + " [Special]"
            
        df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
        mask = (df_past['ParsedDate'] >= pd.to_datetime(past_start)) & (df_past['ParsedDate'] <= pd.to_datetime(TODAY))
        df_past = df_past[mask]
        
        actionable_verbs = ['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign']
        pattern = '|'.join(actionable_verbs)
        df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]

        if not bypass:
            df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(TRACKED_BILLS)]
        else:
            df_past = df_past.tail(150)
        
        for _, row in df_past.iterrows():
            outcome_text = str(row[desc_col])
            
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
            
            # --- HOUSE VS SENATE FLOOR SPLIT ---
            if committee_name == "Floor Action":
                if str(row['CleanBill']).startswith('H'):
                    committee_name = "House Floor"
                elif str(row['CleanBill']).startswith('S'):
                    committee_name = "Senate Floor"

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
        comm_col = next((c for c in df_future.columns if 'com' in c.lower()), None)
        seq_col = next((c for c in df_future.columns if 'seq' in c.lower() or 'order' in c.lower()), 'Sequence')
        
        df_future['CleanBill'] = df_future[bill_col].astype(str).str.replace(' ', '').str.upper()
        
        if 'Is_Special' in df_future.columns:
            df_future.loc[df_future['Is_Special'] == True, 'CleanBill'] = df_future['CleanBill'] + " [Special]"
        
        if not bypass:
            df_future = df_future[df_future['CleanBill'].str.split(' ').str[0].isin(TRACKED_BILLS)]
        else:
            df_future = df_future.head(150)
            
        for _, row in df_future.iterrows():
            processed_events.append({
                "Date": pd.to_datetime(row[date_col]).strftime('%Y-%m-%d'), 
                "Time": "TBD", 
                "Committee": row.get(comm_col, "Unknown Committee") if comm_col else "Unknown Committee", 
                "Bill": row['CleanBill'], 
                "Outcome": "Pending Hearing", 
                "AgendaOrder": row.get(seq_col, 0), 
                "IsFuture": True
            })

    # --- THE CAUCUS & FLOOR BYPASS (WITH SCHEMA ARMOR) ---
    if not df_sched.empty:
        # Schema Armor to prevent KeyErrors if columns are missing
        for col in ['ScheduleDate', 'OwnerName', 'ScheduleTime', 'ScheduleDesc']:
            if col not in df_sched.columns:
                df_sched[col] = ''
                
        for _, row in df_sched.iterrows():
            owner = str(row.get('OwnerName', '')).strip()
            desc = str(row.get('ScheduleDesc', '')).strip()
            
            if any(k in owner.lower() for k in ["caucus", "session", "floor"]) or "session" in desc.lower():
                sched_date = pd.to_datetime(row.get('ScheduleDate', '1970-01-01'), errors='coerce')
                
                time_val = str(row.get('ScheduleTime', '')).strip()
                if not time_val or time_val.lower() in ['nan', 'none']:
                    time_val = desc if desc else "Time TBA"
                
                processed_events.append({
                    "Date": sched_date.strftime('%Y-%m-%d'), 
                    "Time": time_val, 
                    "Committee": owner if owner else "Chamber Event", 
                    "Bill": "📌 " + (desc if desc else "Mandatory Attendance"), 
                    "Outcome": "", 
                    "AgendaOrder": -1, 
                    "IsFuture": sched_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d'))
                })

    master_df = pd.DataFrame(processed_events)
    
    # --- SMART TIME MERGE (Enterprise Regex Normalization) ---
    if not master_df.empty and not df_sched.empty:
        df_sched['MergeDate'] = pd.to_datetime(df_sched['ScheduleDate'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Enterprise Regex Normalization
        def normalize_comm(name):
            if pd.isna(name) or not name: return ""
            n = str(name).lower()
            n = n.replace('floor', 'session')
            # Strip stop words safely using word boundaries
            n = re.sub(r'\b(house|senate|committee|of|the|and|for|on)\b', '', n)
            # Annihilate all non-alphanumeric characters (spaces, commas, ampersands, dashes)
            n = re.sub(r'[^a-z0-9]', '', n)
            return n
            
        master_df['MergeComm'] = master_df['Committee'].apply(normalize_comm)
        df_sched['MergeComm'] = df_sched['OwnerName'].apply(normalize_comm)
        
        # Grab the time, but if the API left it blank, pull it from the description
        df_sched['BestTime'] = df_sched['ScheduleTime'].replace('', pd.NA).fillna(df_sched['ScheduleDesc'])
        
        # Deduplicate to prevent Pandas merge multiplication
        sched_unique = df_sched.dropna(subset=['BestTime']).drop_duplicates(subset=['MergeDate', 'MergeComm'])
        
        # Left Join
        merged = pd.merge(master_df, sched_unique[['MergeDate', 'MergeComm', 'BestTime']], 
                          left_on=['Date', 'MergeComm'], 
                          right_on=['MergeDate', 'MergeComm'], 
                          how='left')
                          
        # Overwrite "Ledger" or "TBD" ONLY if the API successfully found a matching time
        master_df['Time'] = merged['BestTime'].where(merged['BestTime'].notna() & (merged['BestTime'] != ''), master_df['Time'])
        
        master_df = master_df.drop(columns=['MergeComm'])

    return master_df

# ==========================================
# 4. UI RENDERING (Automated)
# ==========================================
raw_payload = fetch_live_data(session_context_list)

for flag in raw_payload["status_flags"]:
    st.warning(f"🏛️ **Notice:** {flag} Expect limited dockets for that session.")
    
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
                st.info("No meetings.")
            else:
                day_events = day_events.sort_values(by='DateTime_Sort')
                for (committee, time_str), group_df in day_events.groupby(['Committee', 'Time'], sort=False):
                    with st.container(border=True):
                        st.markdown(f"**{committee}**\n🕰️ *{time_str}*")
                        st.markdown("---")
                        if is_future_tab: group_df = group_df.sort_values(by='AgendaOrder')
                        
                        for _, row in group_df.iterrows():
                            # UI FIX: If it's a Chamber Event, don't render the outcome, just the Bill/Desc
                            if row['AgendaOrder'] == -1:
                                st.markdown(f"*{row['Bill']}*")
                            else:
                                st.markdown(f"**{row['Bill']}**")
                                if is_future_tab: 
                                    st.caption(f"📑 *Item #{int(row['AgendaOrder'])}*")
                                else: 
                                    st.caption(f"🔹 *{row['Outcome']}*")

tab_past, tab_future = st.tabs(["⏪ Past Week", "⏩ Future Week"])
with tab_past: render_kanban_week(past_start, TODAY - timedelta(days=1), final_df, False)
with tab_future: render_kanban_week(TODAY, future_end, final_df, True)
