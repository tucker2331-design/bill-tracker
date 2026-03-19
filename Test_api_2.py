import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

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
    
    # Create layout columns for the visual ETL pipeline
    ext_col, trans_col = st.columns(2)
    
    with st.spinner("Executing Data Extraction..."):
        try:
            # ==========================================
            # 1. EXTRACT: Stream A (Bill Events)
            # ==========================================
            event_url = "https://lis.virginia.gov/api/v1/legislationevent/getlegislationeventsasync"
            event_params = {"sessionCode": session_code, "billNumber": test_bill}
            
            event_res = requests.get(event_url, headers=HEADERS, params=event_params, timeout=10)
            
            # Using dummy data fallback JUST IN CASE the endpoint name is slightly different in your Postman
            events_data = []
            if event_res.status_code == 200:
                events_data = event_res.json()
            else:
                st.warning(f"Event API returned {event_res.status_code}. Using fallback CSV parsing logic for theory test.")
                # Mocking the data we know exists in HISTORY.CSV for the sake of the merge test
                events_data = [
                    {"BillNumber": test_bill, "EventDate": "2026-03-05T00:00:00", "CommitteeName": "House Courts of Justice", "Description": "Reported out of Courts of Justice (15-Y 0-N)"},
                    {"BillNumber": test_bill, "EventDate": "2026-03-08T00:00:00", "CommitteeName": "House Finance", "Description": "Continued to 2027"}
                ]
            
            df_events = pd.DataFrame(events_data)
            # Clean the date for the merge (Strip the timestamp to just YYYY-MM-DD)
            df_events['MergeDate'] = pd.to_datetime(df_events.get('EventDate', df_events.get('Date'))).dt.strftime('%Y-%m-%d')
            
            with ext_col:
                st.subheader("📥 Stream A: Events Extracted")
                st.dataframe(df_events[['BillNumber', 'MergeDate', 'CommitteeName', 'Description']], use_container_width=True)

            # ==========================================
            # 2. EXTRACT: Stream B (The Schedule Times)
            # ==========================================
            schedule_url = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
            sched_params = {"sessionCode": session_code}
            
            sched_res = requests.get(schedule_url, headers=HEADERS, params=sched_params, timeout=10)
            sched_res.raise_for_status()
            df_schedule = pd.DataFrame(sched_res.json())
            
            # Clean the date for the merge
            df_schedule['MergeDate'] = pd.to_datetime(df_schedule['ScheduleDate']).dt.strftime('%Y-%m-%d')
            
            with ext_col:
                st.subheader("📥 Stream B: Schedule Extracted")
                st.write(f"Total Meetings loaded into memory: {len(df_schedule)}")
                # Show a sample of the raw schedule
                st.dataframe(df_schedule[['OwnerName', 'MergeDate', 'ScheduleTime', 'Description']].head(3), use_container_width=True)


            # ==========================================
            # 3. TRANSFORM: The Pandas Merge
            # ==========================================
            # We join the Events and the Schedule where the Date AND the Committee Name match.
            # This is the stress test: Do their committee names perfectly align between endpoints?
            
            merged_df = pd.merge(
                df_events, 
                df_schedule, 
                how='left', # Keep all events, even if we can't find a time
                left_on=['MergeDate', 'CommitteeName'], 
                right_on=['MergeDate', 'OwnerName']
            )
            
            # Clean up the final calendar dataframe
            final_calendar = merged_df[['MergeDate', 'ScheduleTime', 'CommitteeName', 'BillNumber', 'Description_x', 'Description_y']]
            final_calendar.columns = ['Date', 'Time', 'Committee', 'Bill', 'Outcome', 'Room/Location Notes']
            
            with trans_col:
                st.subheader("✅ TRANSFORM: Final Merged Calendar")
                st.markdown("If the logic holds, we successfully mapped the time and room to the historical event!")
                st.dataframe(final_calendar, use_container_width=True)
                
                # The Stress Test Evaluation
                missing_times = final_calendar['Time'].isna().sum()
                if missing_times > 0:
                    st.error(f"⚠️ **Stress Test Warning:** {missing_times} events failed to find a matching meeting time. This usually happens because 'House Courts of Justice' in Stream A is just called 'Courts of Justice' in Stream B. We will need an alias mapping dictionary in the final backend.")
                else:
                    st.success("🎯 **Flawless Merge!** All events successfully mapped to their scheduled times.")

        except Exception as e:
            st.error(f"Pipeline Failure: {e}")
