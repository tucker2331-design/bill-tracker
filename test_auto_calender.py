import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Legislative Calendar (Enterprise Pipeline)", layout="wide")
st.title("📅 Enterprise Calendar: Live Production")
st.markdown("Reading pre-compiled State Machine data directly from the backend worker.")

# --- UI Controls ---
st.sidebar.header("⚙️ System Controls")
bypass_filter = st.sidebar.toggle("⚠️ Bypass Portfolio (Load All Data)", value=True) 
TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

test_start_date = datetime(2026, 3, 4)

# --- DATA CONNECTION ---
SHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"

@st.cache_data(ttl=60) # Caches for 60 seconds for lightning-fast loads
def load_calendar_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"Failed to load database: {e}")
        return pd.DataFrame()

final_df = load_calendar_data()

if final_df.empty:
    st.info("No actionable events found or Database empty.")
    st.stop()

# Apply the Portfolio Filter (Restored from your previous UI)
if not bypass_filter:
    final_df = final_df[final_df['Bill'].str.split(' ').str[0].isin(TRACKED_BILLS)]
    if final_df.empty:
        st.info("No tracked bills found in the current window.")
        st.stop()

# Sort for the UI
final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + final_df['Time'].replace('Ledger', '11:59 PM').replace('Time TBA', '11:59 PM'), errors='coerce')

# --- 100% PRESERVED KANBAN UI ---
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
                            if "⚠️" in committee:
                                st.markdown(f"<span style='color:#ffa500; font-weight:bold;'>{committee}</span><br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                            else:
                                st.markdown(f"**{committee}**<br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                        
                        if not is_cancelled:
                            skeleton_items = group_df[group_df['Source'].astype(str).str.startswith('API')]
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
