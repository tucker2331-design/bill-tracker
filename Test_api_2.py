import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import io
import re

st.set_page_config(page_title="Legislative Calendar (Enterprise Pipeline)", layout="wide")
st.title("📅 Enterprise Calendar: State Machine Validation")
st.markdown("Testing Chamber Shift Overrides and Strict Parser Expansion.")

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

test_start_date = datetime(2026, 3, 4)
test_end_date = datetime(2026, 3, 10)

# ==========================================
# 2. THE EXTRACTOR (Hardened State Machine)
# ==========================================
@st.cache_data(ttl=600)
def build_state_machine_calendar(tracked_bills, bypass):
    master_events = []
    convene_times = {} 
    
    def safe_fetch_csv(url):
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                raw_text = res.content.decode('iso-8859-1')
                df = pd.read_csv(io.StringIO(raw_text))
                return df.rename(columns=lambda x: x.strip())
        except: pass
        return pd.DataFrame()

    with st.spinner("📥 Processing Chamber Overrides..."):
        api_code = "261"
        blob_code = "20261"
        
        rosetta_stone = LOCAL_LEXICON.copy()
        try:
            for chamber in ['H', 'S']:
                comm_res = requests.get("https://lis.virginia.gov/Committee/api/getcommitteelistasync", headers=HEADERS, params={"sessionCode": api_code, "chamberCode": chamber}, timeout=3)
                if comm_res.status_code == 200:
                    c_data = comm_res.json()
                    if isinstance(c_data, dict): c_data = next((v for v in c_data.values() if isinstance(v, list)), [])
                    for c in c_data:
                        if isinstance(c, dict):
                            prefix = "House " if chamber == 'H' else "Senate "
                            official_name = prefix + str(c.get('ComDes', '')).strip()
                            com_des = str(c.get('ComDes', '')).strip().lower()
                            if com_des and len(com_des) > 3 and com_des not in ["house", "senate", "floor"]:
                                if official_name not in rosetta_stone: rosetta_stone[official_name] = [com_des]
        except Exception as e: print(f"API Dictionary unreachable.")

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
                    
                    owner_lower = owner_name.lower()
                    if "house convenes" in owner_lower or "house chamber" in owner_lower:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        convene_times[date_str]["House"] = {"Time": time_val, "Name": owner_name}
                    elif "senate convenes" in owner_lower or "senate chamber" in owner_lower:
                        if date_str not in convene_times: convene_times[date_str] = {}
                        convene_times[date_str]["Senate"] = {"Time": time_val, "Name": owner_name}
                    
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
        except Exception as e: print(f"Schedule extraction failed.")

        # --- 3. CSV Stitching ---
        df_past = safe_fetch_csv(f"https://lis.blob.core.windows.net/lisfiles/{blob_code}/HISTORY.CSV")
        if not df_past.empty:
            bill_col = next((c for c in df_past.columns if 'bill' in c.lower()), 'BillNumber')
            date_col = next((c for c in df_past.columns if 'date' in c.lower()), 'HistoryDate')
            desc_col = next((c for c in df_past.columns if 'desc' in c.lower() or 'action' in c.lower()), 'Description')
            
            df_past['CleanBill'] = df_past[bill_col].astype(str).str.replace(' ', '').str.upper()
            df_past['ParsedDate'] = pd.to_datetime(df_past[date_col], errors='coerce')
            
            if not bypass: df_past = df_past[df_past['CleanBill'].str.split(' ').str[0].isin(tracked_bills)]
            
            df_past = df_past.sort_values(by=['ParsedDate'])
            bill_locations = {}

            for _, row in df_past.iterrows():
                bill_num = row['CleanBill']
                outcome_text = str(row[desc_col]).strip()
                outcome_lower = outcome_text.lower()
                date_val = row['ParsedDate']
                date_str = date_val.strftime('%Y-%m-%d')
                
                if outcome_text.startswith('H '): chamber_prefix = "House "
                elif outcome_text.startswith('S '): chamber_prefix = "Senate "
                else: chamber_prefix = "House " if bill_num.startswith('H') else "Senate "
                
                if bill_num not in bill_locations:
                    bill_locations[bill_num] = chamber_prefix + "Floor"

                # ==================================================
                # CHAMBER SHIFT OVERRIDE 
                # Prevents "Cross-Chamber Contamination" by forcing a memory update
                # ==================================================
                if not bill_locations[bill_num].startswith(chamber_prefix):
                    bill_locations[bill_num] = chamber_prefix + "Floor"

                # ==================================================
                # STEP A: DETERMINE EVENT LOCATION (Present Action)
                # ==================================================
                event_location = bill_locations[bill_num] 
                
                matched_committee = None
                for lex_key, aliases in rosetta_stone.items():
                    if lex_key.startswith(chamber_prefix) and any(a in outcome_lower for a in aliases if a):
                        matched_committee = lex_key
                        break
                        
                committee_verbs = ["reported", "referred", "assigned", "continued", "passed by indefinitely", "passed by in", "recommend", "incorporate", "failed to", "stricken", "placed on"]
                if matched_committee and any(v in outcome_lower for v in committee_verbs):
                    event_location = matched_committee

                explicit_floor_phrases = [
                    "read first", "read second", "read third",
                    "passed house", "passed senate", "engrossed", "enrolled",
                    "signed by", "rules suspended", "reading dispensed", "substitute waived",
                    "recommendation received", "governor's recommendation", "conference report",
                    "amendment agreed", "amendments agreed", "substitute agreed", "substitute rejected",
                    "acceded to", "concurred in", "conferees appointed", "conferees:",
                    "passed by for the day", "agreed to by", "received", "taken up for",
                    "amendment rejected", "substitute defeated", "calendar", "committee offered", "floor offered"
                ]
                if any(phrase in outcome_lower for phrase in explicit_floor_phrases):
                    event_location = chamber_prefix + "Floor"
                    
                if "subcommittee recommends" in outcome_lower and not matched_committee:
                    event_location = f"⚠️ [Unmapped Subcommittee] {chamber_prefix}Ledger"

                # ==================================================
                # STEP B: UPDATE STATE MEMORY (Future Actions)
                # ==================================================
                if "referred to" in outcome_lower or "assigned to" in outcome_lower or "placed on" in outcome_lower:
                    if matched_committee:
                        bill_locations[bill_num] = matched_committee
                elif "reported from" in outcome_lower or "discharged from" in outcome_lower:
                    if "referred to" not in outcome_lower and "assigned to" not in outcome_lower: 
                        bill_locations[bill_num] = chamber_prefix + "Floor"

                # ==================================================
                # STEP C: RENDER TO UI
                # ==================================================
                if test_start_date <= date_val <= test_end_date:
                    noise_words = ["impact statement", "substitute printed", "laid on speaker's table", "laid on clerk's desk"]
                    if any(n in outcome_lower for n in noise_words): continue
                    
                    time_val = "Ledger"
                    status = ""
                    
                    api_key = f"{date_str}_{event_location}"
                    if api_key in api_schedule_map:
                        time_val = api_schedule_map[api_key]["Time"]
                        status = api_schedule_map[api_key]["Status"]
                    
                    if event_location == "House Floor":
                        anchor = convene_times.get(date_str, {}).get("House")
                        if anchor:
                            time_val = anchor["Time"]
                            event_location = anchor["Name"] 
                    elif event_location == "Senate Floor":
                        anchor = convene_times.get(date_str, {}).get("Senate")
                        if anchor:
                            time_val = anchor["Time"]
                            event_location = anchor["Name"] 
                        
                    master_events.append({
                        "Date": date_str, "Time": time_val, "Status": status,
                        "Committee": event_location, "Bill": bill_num,
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
# 3. UI RENDERING 
# ==========================================
final_df = build_state_machine_calendar(TRACKED_BILLS, bypass_filter)

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
                            st.markdown(f"~~**{committee}**~~<br><span style='color:#ff4b4b; font-weight:bold;'>CANCELLED</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{committee}**<br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                        
                        if not is_cancelled:
                            skeleton_items = group_df[group_df['Source'].str.startswith('API')]
                            bill_items = group_df[group_df['Source'] == 'CSV']
                            
                            if not skeleton_items.empty:
                                for _, s_row in skeleton_items.iterrows():
                                    if s_row['Bill'] == "📌 No live docket" and not bill_items.empty: continue 
                                    st.markdown("---")
                                    st.markdown(f"*{s_row['Bill']}*")
                                    
                            if not bill_items.empty:
                                with st.expander(f"📜 View Bills ({len(bill_items)})"):
                                    for _, row in bill_items.iterrows():
                                        st.markdown(f"**{row['Bill']}**")
                                        st.caption(f"🔹 *{row['Outcome']}*")

render_kanban_week(test_start_date, final_df)
