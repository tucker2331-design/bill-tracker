import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- PAGE SETUP ---
st.set_page_config(page_title="Legislative Calendar (Enterprise Pipeline)", layout="wide")
st.title("📅 Enterprise Calendar: Live Production")

# --- UI CONTROLS ---
st.sidebar.header("⚙️ System Controls")
bypass_filter = st.sidebar.toggle("⚠️ Bypass Portfolio (Load All Data)", value=True) 
TRACKED_BILLS = ["HB10", "HB863", "SB4", "HB1204", "HB500"]

test_start_date = datetime(2026, 3, 4)

# --- DATA CONNECTION ---
SHEET_ID = "1PQDtaTTUeYv781bx4_ZiehcvbEmUt8t7jFmZYJoJGKM"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet=Sheet1"

@st.cache_data(ttl=60) 
def load_calendar_data():
    try:
        df = pd.read_csv(f"{SHEET_URL}&cache_buster={datetime.now().timestamp()}")
        return df
    except Exception as e:
        st.error(f"Database Access Error. Ensure the Google Sheet is set to 'Anyone with the link can view'.")
        return pd.DataFrame()

final_df = load_calendar_data()

if final_df.empty:
    st.info("Waiting for data... Ensure the GitHub Back End has finished its run.")
    st.stop()

if not bypass_filter:
    final_df = final_df[final_df['Bill'].str.split(' ').str[0].isin(TRACKED_BILLS)]
    if final_df.empty:
        st.warning("No tracked bills found for this window.")
        st.stop()

# --- ROBUST SORTING LOGIC ---
if 'SortTime' not in final_df.columns:
    final_df['SortTime'] = final_df['Time']

# The new backend outputs strict 24H times (e.g., 23:59), making this perfectly seamless
clean_time_series = final_df['SortTime'].replace({'Ledger': '23:59', 'Time TBA': '23:59'})
final_df['DateTime_Sort'] = pd.to_datetime(final_df['Date'] + ' ' + clean_time_series, errors='coerce')

# --- THE KANBAN UI ---
def render_kanban_week(start_date, data):
    days = [(start_date + timedelta(days=i)) for i in range(7)]
    cols = st.columns(7)
    
    for i, current_day in enumerate(days):
        date_str = current_day.strftime('%Y-%m-%d')
        with cols[i]:
            st.markdown(f"### {current_day.strftime('%a')}\n{current_day.strftime('%b %d')}")
            st.markdown("---")
            
            day_events = data[data['Date'] == date_str]
            
            if day_events.empty:
                st.caption("No meetings.")
            else:
                day_events = day_events.sort_values(by='DateTime_Sort')
                for (committee, time_str), group_df in day_events.groupby(['Committee', 'Time'], sort=False):
                    status = group_df.iloc[0].get('Status', '')
                    is_cancelled = str(status).upper() == "CANCELLED"
                    
                    with st.container(border=True):
                        # --- HEADER RENDERING ---
                        if is_cancelled:
                            st.markdown(f"~~**{committee}**~~<br><span style='color:#ff4b4b; font-weight:bold;'>CANCELLED</span>", unsafe_allow_html=True)
                        elif "⚠️" in committee:
                            # DLQ Alert: Highlights unmapped ledger committees in bright orange
                            st.markdown(f"<span style='color:#ff9900; font-weight:bold;'>{committee}</span><br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{committee}**<br><span style='color:#888888; font-style:italic;'>{time_str}</span>", unsafe_allow_html=True)
                        
                        # --- CONTENT RENDERING ---
                        if not is_cancelled:
                            skeleton_items = group_df[group_df['Source'].astype(str).str.contains('API')]
                            bill_items = group_df[group_df['Source'].isin(['CSV', 'DOCKET'])]
                            
                            # Print Meeting Notes / Skeleton Agendas
                            for _, s_row in skeleton_items.iterrows():
                                text = str(s_row['Bill']).strip()
                                generic_phrases = ["(View Meeting)", "(Agenda)", "(Agenda) (View Meeting)", "nan", "None", ""]
                                
                                if text in generic_phrases or "📌" in text:
                                    st.markdown("<small>No agenda listed.</small>", unsafe_allow_html=True)
                                elif "⚠️" in text:
                                    # DLQ Alert: Uses Streamlit's native warning box for corrupt PDFs and unverified times
                                    st.warning(text, icon="⚠️")
                                else:
                                    st.markdown(f"<small>{text}</small>", unsafe_allow_html=True)
                                    
                            # Print Tracked Bills
                            if not bill_items.empty:
                                with st.expander(f"📜 View Bills ({len(bill_items)})"):
                                    for _, row in bill_items.iterrows():
                                        st.markdown(f"**{row['Bill']}**")
                                        if row['Outcome']:
                                            st.caption(f"🔹 *{row['Outcome']}*")

render_kanban_week(test_start_date, final_df)
