import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar (Enterprise Mirror)", layout="wide")
st.title("📅 Enterprise Calendar: Full Mirror Test")
st.markdown("Testing the Enterprise Alias Matrix & Anchor Parsing to eliminate black holes.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE AUTO-ROUTER
# ==========================================
@st.cache_data(ttl=3600)
def get_active_session_codes(merge_upcoming=False):
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
                        current_year = datetime.now().year
                        for s in sessions:
                            raw_code = str(s.get('SessionCode', ''))
                            if len(raw_code) >= 4 and raw_code[:4].isdigit() and int(raw_code[:4]) < (current_year - 1): continue
                            if raw_code == str(default_session.get('SessionCode')): continue
                            
                            events = s.get('SessionEvents', [])
                            convene_event = next((e for e in events if e.get('DisplayName') == "Convene"), None)
                            adjourn_event = next((e for e in events if e.get('DisplayName') == "Adjournment"), None)
                            
                            if convene_event:
                                try:
                                    convene_date = datetime.strptime(convene_event['ActualDate'][:10], '%Y-%m-%d')
                                    if adjourn_event:
                                        adjourn_date = datetime.strptime(adjourn_event['ActualDate'][:10], '%Y-%m-%d')
                                        if datetime.now() <= adjourn_date + timedelta(days=1): active_sessions.append(s)
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
        formatted_sessions.append({
            "blob": blob_code, "api": blob_code[2:], "name": display_name,
            "events": s.get('SessionEvents', []), "is_special": "Special" in display_name or s.get('IsDefault') is False
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
# 2. THE EXTRACTOR (Enterprise Alias Matrix Engine)
# ==========================================
def get_best_committee_match(extracted_text, chamber_prefix, rosetta_keys):
    """The Alias Matrix: Normalizes dirty CSV text and strictly maps to official IDs."""
    if not extracted_text: return None
    
    # Normalize the human text
    ext_clean = extracted_text.lower().replace('&', 'and').replace('committee', '').strip()
    
    # 1. Exact Match Check
    for r_key in rosetta_keys:
        r_clean = r_key.lower().replace('&', 'and').replace('committee', '').strip()
        if ext_clean == r_clean or f"{chamber_prefix.lower()}{ext_clean}" == r_clean:
            return r_key
            
    # 2. Strong Substring Check (Longest names first to prevent partial grabs)
    for r_key in sorted(rosetta_keys, key=len, reverse=True):
        # THE SHIELD: Explicitly block generic Black Hole IDs
        if r_key.lower().strip() in ["house", "senate", "house floor", "senate floor"]: 
            continue
            
        r_clean = r_key.replace(chamber_prefix, '').lower().replace('&', 'and').replace('committee', '').strip()
        
        # If the cleaned extracted text is a strong match for the official base name
        if r_clean and (r_clean in ext_clean or ext_clean in r_clean):
            if r_key.startswith(chamber_prefix):
                return r_key
                
    return None

@st.cache_data(ttl=600)
def build_master_calendar(sessions, tracked_bills, bypass):
    master_events = []
    raw_schedules_dump = []
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=5)
            if res.status_code == 200 and "<?xml" not in res.text[:20]:
                df = pd.read_csv(io.StringIO(res.text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Routing Bills via Enterprise Alias Matrix..."):
        for session in sessions:
            api_code = session["api"]
            blob_code = session["blob"]
            is_special = session["is_special"]
            
            # --- 1. Rosetta Stone (Bulletproofed) ---
            rosetta_stone = {}
            try:
                for chamber in ['H', 'S']:
                    comm_res = requests.get("https://lis.virginia.gov/Committee/api/getcommitteelistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber}, timeout=5)
                    if comm_res.status_code == 200:
                        c_data = comm_res.json()
                        if isinstance(c_data, dict):
                            c_data = next((v for v in c_data.values() if isinstance(v, list)), [])
                        for c in c_data:
                            if isinstance(c, dict):
                                prefix = "House " if chamber == 'H' else "Senate "
                                rosetta_stone[prefix + str(c.get('ComDes', '')).strip()] = c.get('ComCode', '')
            except Exception as e: print(f"Rosetta failed: {e}")

            # --- 2. Build Schedule Skeleton ---
            api_schedule_map = {} 
            try:
                sched_res = requests.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
                if sched_res.status_code == 200:
                    schedules = sched_res.json()
                    if isinstance(schedules, dict): schedules = schedules.get('Schedules', [])
                    raw_schedules_dump.extend(schedules)
                    
                    for meeting in schedules:
                        meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                        
                        # Speed filter
                        if not (past_week_2_start <= meeting_date <= future_end): continue
                            
                        date_str = meeting_date.strftime('%Y-%m-%d')
                        owner_name = str(meeting.get('OwnerName', '')).strip()
                        chamber = meeting.get('ChamberCode')
                        if not chamber: chamber = 'S' if 'Senate' in owner_name else 'H'
                        
                        is_cancelled = meeting.get('IsCancelled', False)
                        status = "CANCELLED" if is_cancelled else ""
                        
                        raw_time = str(meeting.get('ScheduleTime', '')).strip()
                        raw_desc = str(meeting.get('Description', meeting.get('ScheduleDesc', ''))).strip()
                        clean_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()
                        
                        time_val = raw_time
                        dynamic_markers = ["upon adjournment", "minutes after", "to be determined", "tba"]
                        if any(marker in clean_desc.lower() for marker in dynamic_markers):
                            parts = clean_desc.split(';')
                            for part in parts:
                                if any(marker in part.lower() for marker in dynamic_markers):
                                    time_val = part.strip()
                                    break
                        if not time_val: time_val = "Time TBA"
                        
                        api_schedule_map[f"{date_str}_{owner_name}"] = {"Time": time_val, "Status": status}
                        
                        if any(k in owner_name.lower() for k in ["caucus", "session", "floor", "convenes", "adjourned"]):
                            master_events.append({
                                "Date": date_str, "Time": time_val, "Status": status,
                                "Committee": owner_name if owner_name else "Chamber Event",
                                "Bill": "📌 " + clean_desc,
                                "Outcome": "", "AgendaOrder": -1,
                                "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                            })
                            continue
                        
                        committee_id = meeting.get('CommitteeNumber', meeting.get('CommitteeCode'))
                        if not committee_id:
                            committee_id = rosetta_stone.get(owner_name)
                            if not committee_id and "-" in owner_name:
                                parent_name = owner_name.split('-')[0].strip()
                                committee_id = rosetta_stone.get(parent_name)
                            
                        has_docket_bills = False
                        if committee_id and not is_cancelled:
                            doc_res = requests.get("https://lis.virginia.gov/Committee/api/getdocketlistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber, "committeeID": committee_id}, timeout=5)
                            if doc_res.status_code == 200 and doc_res.json():
                                agendas = doc_res.json()
                                has_docket_bills = True
                                for item in agendas:
                                    bill_num = str(item.get('LegislationNumber', '')).replace(' ', '').upper()
                                    if is_special: bill_num += " [Special]"
                                    if bypass or bill_num.split(' ')[0] in tracked_bills:
                                        master_events.append({
                                            "Date": date_str, "Time": time_val, "Status": status,
                                            "Committee": owner_name, "Bill": bill_num,
                                            "Outcome": item.get('Description', 'Pending Hearing'),
                                            "AgendaOrder": item.get('Sequence', 0),
                                            "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                                        })
                        
                        if not has_docket_bills:
                            master_events.append({
                                "Date": date_str, "Time": time_val, "Status": status,
                                "Committee": owner_name, "Bill": "📌 No live docket",
                                "Outcome": "", "AgendaOrder": -1,
                                "IsFuture": meeting_date >= pd.to_datetime(TODAY.strftime('%Y-%m-%d')), "Source": "API"
                            })
            except Exception as e: print(f"Schedule extraction failed: {e}")

            # --- 3. CSV Stitching (Anchor Extraction) ---
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
                
                pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign', 'agreed', 'read'])
                df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
                
                if not bypass: df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(tracked_bills)]
                
                for _, row in df_past.iterrows():
                    outcome_text = str(row[desc_col])
                    outcome_lower = outcome_text.lower()
                    date_str = row['ParsedDate'].strftime('%Y-%m-%d')
                    chamber_prefix = "House " if str(row['CleanBill']).startswith('H') else "Senate "
                    
                    committee_name = None
                    
                    # 1. THE SCALPEL: Anchor Regex Parsing
                    # Looks only for the proper noun immediately following procedural verbs
                    anchor_pattern = r'(?:reported from|referred to|rereferred to|re-referred to|discharged from|assigned to)\s+([a-zA-Z\s,&]+?)(?:\(|with|by|,|$)'
                    match = re.search(anchor_pattern, outcome_lower)
                    
                    if match:
                        raw_extracted = match.group(1).strip()
                        matched_committee = get_best_committee_match(raw_extracted, chamber_prefix, rosetta_stone.keys())
                        if matched_committee:
                            committee_name = matched_committee

                    # 2. Floor Action Catch-All
                    floor_keywords = ["passed", "agreed", "engrossed", "read third", "signed", "enrolled", "reconsideration"]
                    if not committee_name and any(k in outcome_lower for k in floor_keywords):
                        committee_name = chamber_prefix + "Floor"
                    
                    # 3. Ultimate Fallback
                    if not committee_name:
                        committee_name = chamber_prefix + "Floor" # Default routing if deeply mangled

                    time_val = "Ledger"
                    status = ""
                    api_key = f"{date_str}_{committee_name}"
                    
                    if api_key in api_schedule_map:
                        time_val = api_schedule_map[api_key]["Time"]
                        status = api_schedule_map[api_key]["Status"]
                        
                    master_events.append({
                        "Date": date_str, "Time": time_val, "Status": status,
                        "Committee": committee_name, "Bill": row['CleanBill'],
                        "Outcome": outcome_text, "AgendaOrder": 999,
                        "IsFuture": False, "Source": "CSV"
                    })

    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        final_df = final_df[~((final_df['Bill'] == "📌 No live docket") & 
                              final_df.duplicated(subset=['Date', 'Committee'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
    return final_df, raw_schedules_dump

# ==========================================
# 3. UI RENDERING & INSPECTOR
# ==========================================
final_df, raw_schedules = build_master_calendar(session_context_list, TRACKED_BILLS, bypass_filter)

# --- DEBUGGER SIDEBAR ---
st.sidebar.header("🛠️ Raw Data Inspector")
if st.sidebar.checkbox("Show Raw Schedule API JSON"):
    if raw_schedules:
        st.sidebar.write("Inspect keys like `ScheduleTime` and `IsCancelled`:")
        st.sidebar.json(raw_schedules[:25])
    else:
        st.sidebar.warning("No API schedule data found for this period.")

if final_df.empty:
    st.info("No actionable events found in the current timeframe.")
    st.stop()
    
final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('Ledger', '11:59 PM').replace('Time TBA', '11:59 PM'), errors='coerce')

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
                    status = group_df.iloc[0]['Status']
                    is_cancelled = status == "CANCELLED"
                    
                    with st.container(border=True):
                        if is_cancelled:
                            st.markdown(f"~~**{committee}**~~\n<br><span style='color:#ff4b4b; font-weight:bold;'>CANCELLED</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{committee}**\n🕰️ *{time_str}*")
                        
                        if is_future_tab: group_df = group_df.sort_values(by='AgendaOrder')
                        
                        if not is_cancelled:
                            if len(group_df) == 1 and group_df.iloc[0]['AgendaOrder'] == -1:
                                st.markdown("---")
                                st.markdown(f"*{group_df.iloc[0]['Bill']}*")
                            else:
                                with st.expander(f"📜 View Bills ({len(group_df)})"):
                                    for _, row in group_df.iterrows():
                                        st.markdown(f"**{row['Bill']}**")
                                        if is_future_tab: st.caption(f"📑 *Item #{int(row['AgendaOrder'])}*")
                                        else: st.caption(f"🔹 *{row['Outcome']}*")

tab_past_2, tab_past_1, tab_future = st.tabs(["⏪ Two Weeks Ago", "⏪ Past Week", "⏩ Future Week"])

with tab_past_2: render_kanban_week(past_week_2_start, past_week_1_start - timedelta(days=1), final_df, False)
with tab_past_1: render_kanban_week(past_week_1_start, TODAY - timedelta(days=1), final_df, False)
with tab_future: render_kanban_week(TODAY, future_end, final_df, True)
