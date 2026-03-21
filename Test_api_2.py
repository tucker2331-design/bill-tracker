import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar (Enterprise Pipeline)", layout="wide")
st.title("📅 Enterprise Calendar: Full Spectrum 7-Day Test")
st.markdown("Testing the Local Lexicon, Inside-Out Parsing, and the Orphan Safety Net.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE ENTERPRISE LOCAL LEXICON
# ==========================================
# Hardcoded safety net to prevent 404 API crashes from destroying the pipeline
LOCAL_LEXICON = {
    "House Appropriations": ["appropriations"],
    "House Courts of Justice": ["courts of justice"],
    "House Rules": ["rules"],
    "House Finance": ["finance"],
    "House Counties, Cities and Towns": ["counties, cities and towns"],
    "House Privileges and Elections": ["privileges and elections"],
    "House Public Safety": ["public safety"],
    "House Communications, Technology and Innovation": ["communications", "technology"],
    "House Education": ["education"],
    "House Agriculture, Chesapeake and Natural Resources": ["agriculture", "natural resources"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"],
    "Senate Rules": ["rules"],
    "Senate Rehabilitation and Social Services": ["rehabilitation and social services", "rehabilitation"],
    "Senate Local Government": ["local government"],
    "Senate Privileges and Elections": ["privileges and elections"],
    "Senate Education and Health": ["education and health"],
    "Senate Commerce and Labor": ["commerce and labor"]
}

# --- UI Controls & 7-Day Window ---
st.sidebar.header("⚙️ System Controls")
bypass_filter = st.sidebar.toggle("⚠️ Bypass Portfolio (Load All Data)", value=True) 

TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

# 7-Day Target Window
test_start_date = datetime(2026, 3, 4)
test_end_date = datetime(2026, 3, 10)

# ==========================================
# 2. THE EXTRACTOR (Live Overlay Engine)
# ==========================================
@st.cache_data(ttl=600)
def build_master_calendar(tracked_bills, bypass):
    master_events = []
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                raw_text = res.content.decode('iso-8859-1')
                df = pd.read_csv(io.StringIO(raw_text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Booting Live Overlay & Inside-Out Parser..."):
        api_code = "261"
        blob_code = "20261"
        
        # --- 1. Hybrid Rosetta Stone ---
        rosetta_stone = LOCAL_LEXICON.copy()
        try:
            for chamber in ['H', 'S']:
                comm_res = requests.get("https://lis.virginia.gov/Committee/api/getcommitteelistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber}, timeout=3)
                if comm_res.status_code == 200:
                    c_data = comm_res.json()
                    if isinstance(c_data, dict):
                        c_data = next((v for v in c_data.values() if isinstance(v, list)), [])
                    for c in c_data:
                        if isinstance(c, dict):
                            prefix = "House " if chamber == 'H' else "Senate "
                            official_name = prefix + str(c.get('ComDes', '')).strip()
                            if official_name not in rosetta_stone:
                                rosetta_stone[official_name] = [str(c.get('ComDes', '')).strip().lower()]
        except Exception as e:
            print(f"API Dictionary unreachable. Falling back to Local Lexicon. Error: {e}")

        # --- 2. API Schedule Skeleton (The Frame) ---
        api_schedule_map = {} 
        try:
            sched_res = requests.get("https://lis.virginia.gov/Schedule/api/getschedulelistasync", headers=HEADERS, params={"sessionCode": api_code}, timeout=5)
            if sched_res.status_code == 200:
                schedules = sched_res.json()
                if isinstance(schedules, dict): schedules = schedules.get('Schedules', [])
                
                for meeting in schedules:
                    meeting_date = pd.to_datetime(meeting.get('ScheduleDate', '1970-01-01'), errors='coerce')
                    
                    if not (test_start_date <= meeting_date <= test_end_date): continue
                        
                    date_str = meeting_date.strftime('%Y-%m-%d')
                    owner_name = str(meeting.get('OwnerName', '')).strip()
                    is_cancelled = meeting.get('IsCancelled', False)
                    status = "CANCELLED" if is_cancelled else ""
                    
                    raw_time = str(meeting.get('ScheduleTime', '')).strip()
                    clean_desc = re.sub(r'<[^>]+>', '', str(meeting.get('Description', ''))).strip()
                    
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
                            "Outcome": "", "AgendaOrder": -1, "Source": "API"
                        })
                        continue
                        
                    master_events.append({
                        "Date": date_str, "Time": time_val, "Status": status,
                        "Committee": owner_name, "Bill": "📌 No live docket",
                        "Outcome": "", "AgendaOrder": -1, "Source": "API_Skeleton"
                    })
        except Exception as e: print(f"Schedule extraction failed: {e}")

        # --- 3. CSV Stitching (Inside-Out Parsing & Orphan Net) ---
        df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
        if not df_past.empty:
            bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
            date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
            desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
            
            df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
            df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
            
            mask = (df_past['ParsedDate'] >= test_start_date) & (df_past['ParsedDate'] <= test_end_date)
            df_past = df_past[mask]
            
            pattern = '|'.join(['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign', 'agreed', 'read', 'refer'])
            df_past = df_past[df_past[desc_col].str.contains(pattern, case=False, na=False)]
            
            if not bypass: df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(tracked_bills)]
            
            for _, row in df_past.iterrows():
                outcome_text = str(row[desc_col]).strip()
                outcome_lower = outcome_text.lower()
                date_str = row['ParsedDate'].strftime('%Y-%m-%d')
                
                # Crossover Anchor Lock
                if outcome_text.startswith('H '): chamber_prefix = "House "
                elif outcome_text.startswith('S '): chamber_prefix = "Senate "
                else: chamber_prefix = "House " if str(row['CleanBill']).startswith('H') else "Senate "
                
                committee_name = None
                
                # THE INSIDE-OUT PARSER
                procedural_verbs = ["reported", "referred", "assigned", "continued", "passed by"]
                if any(verb in outcome_lower for verb in procedural_verbs):
                    matched_key = None
                    # Search inside the messy string for any known Lexicon alias
                    for lex_key, lex_aliases in rosetta_stone.items():
                        if lex_key.startswith(chamber_prefix):
                            for alias in lex_aliases:
                                if alias in outcome_lower:
                                    matched_key = lex_key
                                    break
                        if matched_key: break
                    
                    if matched_key:
                        committee_name = matched_key

                # Floor Routing
                floor_keywords = ["passed", "agreed", "engrossed", "read third", "signed", "enrolled", "reconsideration"]
                if not committee_name and any(k in outcome_lower for k in floor_keywords):
                    committee_name = chamber_prefix + "Floor"
                
                # THE ORPHAN SAFETY NET
                if not committee_name:
                    committee_name = f"⚠️ [Orphan] {chamber_prefix}Ledger"

                time_val = "Ledger"
                status = ""
                api_key = f"{date_str}_{committee_name}"
                
                if api_key in api_schedule_map:
                    time_val = api_schedule_map[api_key]["Time"]
                    status = api_schedule_map[api_key]["Status"]
                    
                master_events.append({
                    "Date": date_str, "Time": time_val, "Status": status,
                    "Committee": committee_name, "Bill": row['CleanBill'],
                    "Outcome": outcome_text, "AgendaOrder": 999, "Source": "CSV"
                })

    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        # Clear out "No live docket" placeholders if a bill successfully routed to that committee
        final_df = final_df[~((final_df['Bill'] == "📌 No live docket") & 
                              final_df.duplicated(subset=['Date', 'Committee'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
    return final_df

# ==========================================
# 3. UI RENDERING 
# ==========================================
final_df = build_master_calendar(TRACKED_BILLS, bypass_filter)

if final_df.empty:
    st.info("No actionable events found in the 7-day window.")
    st.stop()
    
final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('Ledger', '11:59 PM').replace('Time TBA', '11:59 PM'), errors='coerce')

def render_kanban_week(start_date, data):
    days = [(start_date + timedelta(days=i)) for i in range(7)]
    cols = st.columns(7)
    
    for i, current_day in enumerate(days):
        date_str = current_day.strftime('%Y-%m-%d')
        with cols[i]:
            st.markdown(f"**{current_day.strftime('%a, %b %d')}**")
            st.markdown("---")
            
            day_events = data[data['Date'] == date_str]
            
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
                            # Highlight Orphans in orange
                            if "⚠️ [Orphan]" in committee:
                                st.markdown(f"<span style='color:#ffa500; font-weight:bold;'>{committee}</span>\n🕰️ *{time_str}*", unsafe_allow_html=True)
                            else:
                                st.markdown(f"**{committee}**\n🕰️ *{time_str}*")
                        
                        if not is_cancelled:
                            if len(group_df) == 1 and group_df.iloc[0]['AgendaOrder'] == -1:
                                st.markdown("---")
                                st.markdown(f"*{group_df.iloc[0]['Bill']}*")
                            else:
                                with st.expander(f"📜 View Bills ({len(group_df)})"):
                                    for _, row in group_df.iterrows():
                                        st.markdown(f"**{row['Bill']}**")
                                        st.caption(f"🔹 *{row['Outcome']}*")

render_kanban_week(test_start_date, final_df)
