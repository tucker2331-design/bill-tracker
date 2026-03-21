import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar (Enterprise Pipeline)", layout="wide")
st.title("📅 Enterprise Calendar: Final Matrix Validation")
st.markdown("Testing the Expanded Lexicon, Floor Anchoring, and UI Polish.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# ==========================================
# 1. THE ENTERPRISE LOCAL LEXICON
# ==========================================
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
    "House General Laws": ["general laws"],
    "House Transportation": ["transportation"],
    "House Labor and Commerce": ["labor and commerce", "labor"],
    "House Health and Human Services": ["health and human services", "health"],
    "Senate Finance and Appropriations": ["finance and appropriations", "finance"],
    "Senate Courts of Justice": ["courts of justice"],
    "Senate Rules": ["rules"],
    "Senate Rehabilitation and Social Services": ["rehabilitation and social services", "rehabilitation"],
    "Senate Local Government": ["local government"],
    "Senate Privileges and Elections": ["privileges and elections"],
    "Senate Education and Health": ["education and health", "education", "health"],
    "Senate Commerce and Labor": ["commerce and labor", "commerce"],
    "Senate General Laws and Technology": ["general laws and technology", "general laws"],
    "Senate Transportation": ["transportation"],
    "Senate Agriculture, Conservation and Natural Resources": ["agriculture", "conservation", "natural resources"]
}

# --- UI Controls ---
st.sidebar.header("⚙️ System Controls")
bypass_filter = st.sidebar.toggle("⚠️ Bypass Portfolio (Load All Data)", value=True) 
TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

# 7-Day Target Window
test_start_date = datetime(2026, 3, 4)
test_end_date = datetime(2026, 3, 10)

# ==========================================
# 2. THE EXTRACTOR 
# ==========================================
@st.cache_data(ttl=600)
def build_master_calendar(tracked_bills, bypass):
    master_events = []
    convene_times = {} # THE TIME-ANCHOR VAULT
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                raw_text = res.content.decode('iso-8859-1')
                df = pd.read_csv(io.StringIO(raw_text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Compiling Matrix and Anchoring Floor Sessions..."):
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
                            com_des = str(c.get('ComDes', '')).strip().lower()
                            
                            if com_des and len(com_des) > 3 and com_des not in ["house", "senate", "floor"]:
                                if official_name not in rosetta_stone:
                                    rosetta_stone[official_name] = [com_des]
        except Exception as e: print(f"API Dictionary unreachable. Using Lexicon. Error: {e}")

        # --- 2. API Schedule Skeleton ---
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
                    dynamic_markers = ["upon adjournment", "minutes after", "to be determined", "tba", "recess"]
                    if any(marker in clean_desc.lower() for marker in dynamic_markers):
                        parts = clean_desc.split(';')
                        for part in parts:
                            if any(marker in part.lower() for marker in dynamic_markers):
                                time_val = part.strip()
                                break
                    if not time_val: time_val = "Time TBA"
                    
                    # EXTRACT CONVENE TIMES FOR ANCHORING
                    owner_lower = owner_name.lower()
                    if "house convenes" in owner_lower or "house chamber" in owner_lower:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        convene_times[date_str]["House"] = time_val
                    elif "senate convenes" in owner_lower or "senate chamber" in owner_lower:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        convene_times[date_str]["Senate"] = time_val
                    
                    # THE TIME-SPLIT LOCK
                    map_key = f"{date_str}_{owner_name}"
                    if map_key not in api_schedule_map:
                        api_schedule_map[map_key] = {"Time": time_val, "Status": status}
                    
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

        # --- 3. CSV Stitching (Inside-Out Parsing) ---
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
                
                # Inside-Out Matrix Parser
                procedural_verbs = ["reported", "referred", "assigned", "continued", "passed by"]
                if any(verb in outcome_lower for verb in procedural_verbs):
                    matched_key = None
                    for lex_key, lex_aliases in rosetta_stone.items():
                        if lex_key.startswith(chamber_prefix):
                            for alias in lex_aliases:
                                if alias and alias in outcome_lower:
                                    matched_key = lex_key
                                    break
                        if matched_key: break
                    
                    if matched_key:
                        committee_name = matched_key

                # Floor Routing
                floor_keywords = ["passed", "agreed", "engrossed", "read third", "signed", "enrolled", "reconsideration", "suspended", "dispensed", "acceded", "concurred", "amendments"]
                if not committee_name and any(k in outcome_lower for k in floor_keywords):
                    committee_name = chamber_prefix + "Floor"
                
                if not committee_name:
                    committee_name = f"⚠️ [Orphan] {chamber_prefix}Ledger"

                time_val = "Ledger"
                status = ""
                
                # Retrieve Standard API Times
                api_key = f"{date_str}_{committee_name}"
                if api_key in api_schedule_map:
                    time_val = api_schedule_map[api_key]["Time"]
                    status = api_schedule_map[api_key]["Status"]
                
                # ==================================================
                # SURGICAL TIME-ANCHOR FOR FLOOR ACTIONS
                # Intercepts the "Ledger" time and injects the Convenes time
                # ==================================================
                if committee_name == "House Floor":
                    time_val = convene_times.get(date_str, {}).get("House", "Ledger")
                elif committee_name == "Senate Floor":
                    time_val = convene_times.get(date_str, {}).get("Senate", "Ledger")
                    
                master_events.append({
                    "Date": date_str, "Time": time_val, "Status": status,
                    "Committee": committee_name, "Bill": row['CleanBill'],
                    "Outcome": outcome_text, "AgendaOrder": 999, "Source": "CSV"
                })

    final_df = pd.DataFrame(master_events)
    if not final_df.empty:
        final_df = final_df[~((final_df['Bill'] == "📌 No live docket") & 
                              final_df.duplicated(subset=['Date', 'Committee'], keep=False))]
        final_df = final_df.sort_values(by=['Date', 'Committee', 'Bill', 'Source'])
        final_df = final_df.drop_duplicates(subset=['Date', 'Committee', 'Bill'], keep='first')
        
    return final_df

# ==========================================
# 3. UI RENDERING (Polished)
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
                        # UI POLISH: No emojis, time drops cleanly below using raw HTML
                        if is_cancelled:
                            st.markdown(f"~~**{committee}**~~<br><span style='color:#ff4b4b; font-weight:bold;'>CANCELLED</span>", unsafe_allow_html=True)
                        else:
                            if "⚠️ [Orphan]" in committee:
                                st.markdown(f"<span style='color:#ffa500; font-weight:bold;'>{committee}</span><br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"**{committee}**<br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                        
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
