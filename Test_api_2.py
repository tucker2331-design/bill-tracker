import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar (Pure API Sandbox)", layout="wide")
st.title("📅 Enterprise Calendar: Pure API Sandbox")
st.markdown("Testing the Rosetta Stone ID Bridge for flawless Senate & House Agenda extraction.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE AUTO-ROUTER
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
                            if len(raw_code) >= 4 and raw_code[:4].isdigit():
                                if int(raw_code[:4]) < (current_year - 1): continue
                            if raw_code == str(default_session.get('SessionCode')): continue
                                
                            events = s.get('SessionEvents', [])
                            convene_event = next((e for e in events if e.get('DisplayName') == "Convene"), None)
                            adjourn_event = next((e for e in events if e.get('DisplayName') == "Adjournment"), None)
                            
                            if convene_event:
                                try:
                                    convene_date = datetime.strptime(convene_event['ActualDate'][:10], '%Y-%m-%d')
                                    if adjourn_event:
                                        adjourn_date = datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d')
                                        if current_date <= adjourn_date + timedelta(days=1): active_sessions.append(s)
                                    else:
                                        if convene_date.year >= current_year: active_sessions.append(s)
                                except: pass
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
            "blob": blob_code, "api": blob_code[2:], "name": display_name,
            "events": s.get('SessionEvents', []), "is_special": is_special
        })

    if not formatted_sessions:
        current_year = str(datetime.now().year)
        formatted_sessions = [{"blob": f"{current_year}1", "api": f"{current_year[2:]}1", "name": f"{current_year} Regular Session", "events": [], "is_special": False}]
    return formatted_sessions

# --- UI Controls ---
st.sidebar.header("⚙️ System Controls")
merge_sessions_toggle = st.sidebar.toggle("🌉 Merge Upcoming Transition Sessions", value=False)
bypass_filter = st.sidebar.toggle("⚠️ Bypass Portfolio (Load All Data)", value=True) 

session_context_list = get_active_session_codes(merge_upcoming=merge_sessions_toggle)
TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

TODAY = datetime(2026, 3, 20)
past_week_2_start = TODAY - timedelta(days=14)
past_week_1_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE EXTRACTOR (Pure API + Ledger Fallback)
# ==========================================
@st.cache_data(ttl=600)
def build_master_calendar(sessions, tracked_bills, bypass):
    master_events = []
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200 and "<?xml" not in res.text[:20]:
                df = pd.read_csv(io.StringIO(res.text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Syncing Live Enterprise APIs (Building Rosetta Stone)..."):
        for session in sessions:
            api_code = session["api"]
            blob_code = session["blob"]
            is_special = session["is_special"]
            
            # --- STEP 1: Build the Rosetta Stone (Committee ID Bridge) ---
            rosetta_stone = {}
            try:
                comm_url = "https://lis.virginia.gov/Committee/api/getcommitteelistasync"
                comm_res = requests.get(comm_url, headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
                if comm_res.status_code == 200:
                    for c in comm_res.json():
                        rosetta_stone[str(c.get('ComDes')).strip()] = c.get('ComCode')
            except Exception as e:
                print(f"Rosetta Stone failed: {e}")

            # --- STEP 2: Fetch the Master Schedule & Agendas ---
            try:
                sched_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
                sched_res = requests.get(sched_url, headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
                
                if sched_res.status_code == 200:
                    schedules = sched_res.json()
                    if isinstance(schedules, dict): schedules = schedules.get('Schedules', [])
                    
                    for meeting in schedules:
                        meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                        owner_name = str(meeting.get('OwnerName', '')).strip()
                        chamber = meeting.get('ChamberCode')
                        if not chamber: chamber = 'S' if 'Senate' in owner_name else 'H'
                        
                        time_val = meeting.get('ScheduleTime', '')
                        if not time_val: time_val = meeting.get('ScheduleDesc', 'Time TBA')
                        
                        # Bypass for Caucuses / Floor Sessions
                        if any(k in owner_name.lower() for k in ["caucus", "session", "floor"]):
                            master_events.append({
                                "Date": meeting_date.strftime('%Y-%m-%d'), "Time": time_val,
                                "Committee": owner_name if owner_name else "Chamber Event",
                                "Bill": "📌 " + meeting.get('ScheduleDesc', 'Mandatory Attendance'),
                                "Outcome": "", "AgendaOrder": -1,
                                "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')),
                                "Source": "API"
                            })
                            continue
                        
                        # Fetch Agenda using Rosetta Stone
                        committee_id = meeting.get('CommitteeCode') 
                        if not committee_id: committee_id = rosetta_stone.get(owner_name)
                            
                        if committee_id:
                            docket_url = "https://lis.virginia.gov/Committee/api/getdocketlistasync"
                            doc_res = requests.get(docket_url, headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber, "committeeID": committee_id}, timeout=5)
                            
                            if doc_res.status_code == 200:
                                agendas = doc_res.json()
                                for item in agendas:
                                    bill_num = str(item.get('LegislationNumber', '')).replace(' ', '').upper()
                                    if is_special: bill_num += " [Special]"
                                    
                                    if bypass or bill_num.split(' ')[0] in tracked_bills:
                                        master_events.append({
                                            "Date": meeting_date.strftime('%Y-%m-%d'), "Time": time_val,
                                            "Committee": owner_name, "Bill": bill_num,
                                            "Outcome": item.get('Description', 'Pending Hearing'),
                                            "AgendaOrder": item.get('Sequence', 0),
                                            "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')),
                                            "Source": "API"
                                        })
            except Exception as e:
                print(f"Schedule extraction failed: {e}")

            # --- STEP 3: The Ledger Fallback (For past/impromptu events) ---
            df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
            if not df_past.empty:
                bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
                date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
                desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
                
                df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
                if is_special: df_past['CleanBill'] = df_past['CleanBill'] + " [Special]"
                
                df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
                mask = (df_past['ParsedDate'] >= pd.to_datetime(past_week_2_start)) & (df_past['ParsedDate'] <= pd.to_datetime(TODAY))
                df_past = df_past[mask]
                
                pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign'])
                df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
                
                if not bypass: df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(tracked_bills)]
                else: df_past = df_past.tail(150)
                
                for _, row in df_past.iterrows():
                    outcome_text = str(row[desc_col])
                    outcome_lower = outcome_text.lower()
                    
                    committee_name = "Floor Action"
                    if "reported from" in outcome_lower: committee_name = outcome_text[outcome_lower.find("reported from") + 13:]
                    elif "reported out of" in outcome_lower: committee_name = outcome_text[outcome_lower.find("reported out of") + 15:]
                    elif "referred to" in outcome_lower: committee_name = outcome_text[outcome_lower.find("referred to") + 11:]
                    
                    committee_name = committee_name.split('(')[0].split(' with ')[0].strip().title()
                    if committee_name == "Floor Action":
                        committee_name = "House Floor" if str(row['CleanBill']).startswith('H') else "Senate Floor"
                        
                    master_events.append({
                        "Date": row['ParsedDate'].strftime('%Y-%m-%d'), "Time": "Ledger",
                        "Committee": committee_name, "Bill": row['CleanBill'],
                        "Outcome": outcome_text, "AgendaOrder": 999,
                        "IsFuture": False, "Source": "CSV"
                    })

    # --- STEP 4: Deduplicate API vs CSV ---
    # If the API already captured a meeting for a specific date/committee, drop the "Ledger" duplicates to keep the UI clean.
    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        # Sort so API records (which have exact times) are prioritized over CSV "Ledger" records
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
    return final_df

# ==========================================
# 3. UI RENDERING 
# ==========================================
final_df = build_master_calendar(session_context_list, TRACKED_BILLS, bypass_filter)

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
                            if row['AgendaOrder'] == -1:
                                st.markdown(f"*{row['Bill']}*")
                            else:
                                st.markdown(f"**{row['Bill']}**")
                                if is_future_tab: st.caption(f"📑 *Item #{int(row['AgendaOrder'])}*")
                                else: st.caption(f"🔹 *{row['Outcome']}*")

tab_past_2, tab_past_1, tab_future = st.tabs(["⏪ Two Weeks Ago", "⏪ Past Week", "⏩ Future Week"])

with tab_past_2: render_kanban_week(past_week_2_start, past_week_1_start - timedelta(days=1), final_df, False)
with tab_past_1: render_kanban_week(past_week_1_start, TODAY - timedelta(days=1), final_df, False)
with tab_future: render_kanban_week(TODAY, future_end, final_df, True)
