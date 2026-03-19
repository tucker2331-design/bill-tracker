import streamlit as st
import requests
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Enterprise ETL Merge Test", layout="wide")
st.title("🧬 The Hybrid Data Merge Test")
st.markdown("Simulating the backend logic: Merging Historical Events with the Schedule API to generate a Past-Week Calendar.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# Basic Inputs
col1, col2 = st.columns(2)
with col1:
    test_bill = st.text_input("Enter a Tracked Bill (e.g., HB10, SB1):", value="HB10")
with col2:
    session_code = st.text_input("Session Code:", value="261")

if st.button("🚀 Execute Hybrid Merge", type="primary"):
    
    ext_col, trans_col = st.columns(2)
    
    with st.spinner("Executing Data Extraction..."):
        try:
            # ==========================================
            # 1. EXTRACT: Stream A (Bill Events)
            # ==========================================
            event_url = "https://lis.virginia.gov/api/v1/legislationevent/getlegislationeventsasync"
            event_params = {"sessionCode": session_code, "billNumber": test_bill}
            
            event_res = requests.get(event_url, headers=HEADERS, params=event_params, timeout=10)
            
            events_data = None
            try:
                events_data = event_res.json()
            except Exception:
                st.warning(f"⚠️ Stream A (Events) did not return JSON. Status: {event_res.status_code}")
                with st.expander("View Raw Server Response (Events)"):
                    st.code(event_res.text[:1000]) # Print the raw text to see the error
                
            # Fallback to mock data just so we can test the merge logic if the API fails
            if not events_data:
                st.info("Injecting Mock Event Data to test Pandas Merge logic...")
                events_data = [
                    {"BillNumber": test_bill, "EventDate": "2026-03-05T00:00:00", "CommitteeName": "House Courts of Justice", "Description": "Reported out of Courts of Justice (15-Y 0-N)"},
                    {"BillNumber": test_bill, "EventDate": "2026-03-08T00:00:00", "CommitteeName": "House Finance", "Description": "Continued to 2027"}
                ]
            
            df_events = pd.DataFrame(events_data)
            # Standardize date formatting based on whichever key the API/Mock data uses
            date_key = 'ActualDate' if 'ActualDate' in df_events.columns else 'EventDate'
            if date_key not in df_events.columns:
                 date_key = 'Date' # Ultimate fallback
                 
            df_events['MergeDate'] = pd.to_datetime(df_events[date_key], errors='coerce').dt.strftime('%Y-%m-%d')
            
            with ext_col:
                st.subheader("📥 Stream A: Events Extracted")
                display_cols = [c for c in ['BillNumber', 'MergeDate', 'CommitteeName', 'Description'] if c in df_events.columns]
                st.dataframe(df_events[display_cols], use_container_width=True)

            # ==========================================
            # 2. EXTRACT: Stream B (The Schedule Times)
            # ==========================================
            schedule_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            sched_params = {"sessionCode": session_code}
            
            sched_res = requests.get(schedule_url, headers=HEADERS, params=sched_params, timeout=10)
            
            sched_data = None
            try:
                sched_data = sched_res.json()
            except Exception:
                st.error(f"❌ Stream B (Schedule) FATAL ERROR: Did not return JSON. Status: {sched_res.status_code}")
                with st.expander("View Raw Server Response (Schedule)"):
                    st.code(sched_res.text[:1000])
                st.stop() # We cannot merge without the schedule, so we halt here.
                
            df_schedule = pd.DataFrame(sched_data)
            
            # Navigate the JSON tree if it's nested (e.g., inside 'ListItems')
            if 'ListItems' in df_schedule.columns:
                df_schedule = pd.DataFrame(sched_data['ListItems'])
                
            df_schedule['MergeDate'] = pd.to_datetime(df_schedule['ScheduleDate'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            with ext_col:
                st.subheader("📥 Stream B: Schedule Extracted")
                st.write(f"Total Meetings loaded into memory: {len(df_schedule)}")
                st.dataframe(df_schedule[['OwnerName', 'MergeDate', 'ScheduleTime', 'Description']].head(3), use_container_width=True)

            # ==========================================
            # 3. TRANSFORM: The Pandas Merge
            # ==========================================
            st.markdown("---")
            st.subheader("✅ TRANSFORM: Final Merged Calendar")
            
            # The left join
            merged_df = pd.merge(
                df_events, 
                df_schedule, 
                how='left', 
                left_on=['MergeDate', 'CommitteeName'], 
                right_on=['MergeDate', 'OwnerName']
            )
            
            # Safe column renaming based on what actually exists after the merge
            final_cols = []
            rename_dict = {}
            
            if 'MergeDate' in merged_df.columns: final_cols.append('MergeDate'); rename_dict['MergeDate'] = 'Date'
            if 'ScheduleTime' in merged_df.columns: final_cols.append('ScheduleTime'); rename_dict['ScheduleTime'] = 'Time'
            if 'CommitteeName' in merged_df.columns: final_cols.append('CommitteeName'); rename_dict['CommitteeName'] = 'Committee'
            if 'BillNumber' in merged_df.columns: final_cols.append('BillNumber'); rename_dict['BillNumber'] = 'Bill'
            if 'Description_x' in merged_df.columns: final_cols.append('Description_x'); rename_dict['Description_x'] = 'Outcome'
            if 'Description_y' in merged_df.columns: final_cols.append('Description_y'); rename_dict['Description_y'] = 'Room Notes'
            
            final_calendar = merged_df[final_cols].rename(columns=rename_dict)
            
            with trans_col:
                st.dataframe(final_calendar, use_container_width=True)
                
                # Evaluation
                if 'Time' in final_calendar.columns:
                    missing_times = final_calendar['Time'].isna().sum()
                    if missing_times > 0:
                        st.warning(f"⚠️ **{missing_times} events failed to map a time.** This confirms we need a Committee Name Alias Dictionary (e.g., translating 'House Courts of Justice' to 'Courts of Justice').")
                    else:
                        st.success("🎯 **Flawless Merge!** All events successfully mapped to their scheduled times.")
                else:
                    st.error("Merge failed to produce a 'Time' column.")

        except Exception as e:
            st.error(f"Pipeline Failure: {e}")
