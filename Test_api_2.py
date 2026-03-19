import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Set page config for a wide, enterprise dashboard feel
st.set_page_config(page_title="Lobbyist Calendar UI Test", layout="wide", page_icon="📅")

st.title("📅 Legislative Calendar & Outcomes")
st.markdown("Tracking scheduled hearings and past-week outcomes for active portfolio bills.")

# ==========================================
# 1. GENERATE MOCK PIPELINE DATA
# ==========================================
# This exactly mimics the final output of our Hybrid ETL Merge
mock_data = [
    {"Date": "2026-03-05", "Time": "10:00 AM", "Committee": "Courts of Justice", "Bill": "HB10", "Outcome": "Reported out of Courts of Justice (15-Y 0-N)", "Room": "House Room C"},
    {"Date": "2026-03-06", "Time": "2:00 PM", "Committee": "Finance", "Bill": "HB863", "Outcome": "Continued to 2027", "Room": "House Room A"},
    {"Date": "2026-03-08", "Time": "8:30 AM", "Committee": "Appropriations", "Bill": "HB1204", "Outcome": "Incorporated into HB1100", "Room": "House Room B"},
    {"Date": "2026-03-10", "Time": "TBD", "Committee": "Rules", "Bill": "SB4", "Outcome": "Passed by indefinitely in Rules (12-Y 4-N)", "Room": None},
    {"Date": "2026-03-12", "Time": "1:00 PM", "Committee": "Privileges and Elections", "Bill": "HB500", "Outcome": "Hearing Scheduled", "Room": "Senate Room 3"}
]

df = pd.DataFrame(mock_data)

# Ensure Date is formatted cleanly for the UI
df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%b %d, %Y')
# Handle null rooms gracefully
df['Room'] = df['Room'].fillna("TBD")

# ==========================================
# 2. UI FILTERS & METRICS (The $50k Dashboard feel)
# ==========================================
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    # A quick filter to let lobbyists isolate specific days
    date_filter = st.selectbox("Filter by Date:", ["All Dates"] + list(df['Date'].unique()))
with col2:
    # Isolate specific committees
    comm_filter = st.selectbox("Filter by Committee:", ["All Committees"] + list(df['Committee'].unique()))

# Apply the UI filters to the dataframe
if date_filter != "All Dates":
    df = df[df['Date'] == date_filter]
if comm_filter != "All Committees":
    df = df[df['Committee'] == comm_filter]

# ==========================================
# 3. THE DATA RENDERING
# ==========================================
st.subheader(f"📋 Docket & Outcomes ({len(df)} Events)")

# We use Streamlit's new column_config to make the table look highly professional
st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Date": st.column_config.TextColumn("Date", width="small"),
        "Time": st.column_config.TextColumn("Time", width="small"),
        "Bill": st.column_config.TextColumn("Bill #", width="small", help="The tracked legislation"),
        "Committee": st.column_config.TextColumn("Committee", width="medium"),
        "Outcome": st.column_config.TextColumn(
            "Action / Outcome", 
            width="large",
            # We can visually flag bad news like 'Continued' or 'Passed by indefinitely' later with background colors if desired
        ),
        "Room": st.column_config.TextColumn("Location", width="small")
    }
)

# ==========================================
# 4. EXPORT CAPABILITY
# ==========================================
st.markdown("---")
st.download_button(
    label="📥 Download Calendar as CSV",
    data=df.to_csv(index=False).encode('utf-8'),
    file_name='weekly_legislative_calendar.csv',
    mime='text/csv',
)
