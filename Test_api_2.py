import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Rolling Legislative Calendar", layout="wide")

st.title("📅 Rolling Legislative Calendar")
st.markdown("Dynamic 14-day tracking window with sequence-sorted future dockets.")

# ==========================================
# 1. DYNAMIC TIME WINDOW CALCULATION
# ==========================================
TODAY = datetime(2026, 3, 19)

past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE NOISE FILTER (For Past Events Only)
# ==========================================
ACTIONABLE_VERBS = ['report', 'continue', 'pass', 'fail', 'incorporate', 'hearing', 'strike', 'stricken', 'veto', 'sign']

def apply_noise_filter(df):
    if df.empty: return df
    
    # We only run the noise filter on PAST events. 
    # If it's a future event (from the Docket CSV), its mere existence on the docket makes it actionable.
    past_mask = pd.to_datetime(df['Date']).dt.date < TODAY.date()
    
    pattern = '|'.join(ACTIONABLE_VERBS)
    valid_past = df[past_mask & df['Outcome'].str.contains(pattern, case=False, na=False)]
    
    future_events = df[~past_mask] # Keep all future docket items
    
    return pd.concat([valid_past, future_events])

# ==========================================
# 3. TIME-AWARE MOCK DATA
# ==========================================
raw_data = [
    # --- PAST WEEK (From HISTORY.CSV) ---
    {"Date": "2026-03-12", "Time": "10:00 AM", "Committee": "Courts of Justice", "Bill": "HB10", "Outcome": "Reported out of Courts of Justice (15-Y 0-N)", "AgendaOrder": 0},
    {"Date": "2026-03-12", "Time": "10:00 AM", "Committee": "Courts of Justice", "Bill": "HB99", "Outcome": "Continued to 2027", "AgendaOrder": 0},
    {"Date": "2026-03-13", "Time": "08:00 AM", "Committee": "Finance", "Bill": "HB863", "Outcome": "Continued to 2027", "AgendaOrder": 0},
    {"Date": "2026-03-14", "Time": "09:00 AM", "Committee": "Rules", "Bill": "SB4", "Outcome": "Passed by indefinitely in Rules (12-Y 4-N)", "AgendaOrder": 0},
    
    # --- FUTURE WEEK (From DOCKET.CSV) ---
    # Notice we have 3 bills in the same meeting. The UI must sort them by AgendaOrder.
    {"Date": "2026-03-24", "Time": "09:00 AM", "Committee": "Joint Commission on Tech", "Bill": "HB500", "Outcome": "Pending Hearing", "AgendaOrder": 4},
    {"Date": "2026-03-24", "Time": "09:00 AM", "Committee": "Joint Commission on Tech", "Bill": "SB12", "Outcome": "Pending Hearing", "AgendaOrder": 1},
    {"Date": "2026-03-24", "Time": "09:00 AM", "Committee": "Joint Commission on Tech", "Bill": "HB88", "Outcome": "Pending Hearing", "AgendaOrder": 2},
]

df = pd.DataFrame(raw_data)
df['DateTime_Sort'] = pd.to_datetime(df['Date'] + ' ' + df['Time'].replace('TBD', '11:59 PM'), errors='coerce')

clean_df = apply_noise_filter(df)

# ==========================================
# 4. THE UI RENDER ENGINE
# ==========================================
def render_kanban_week(start_date, end_date, data, is_future=False):
    days_in_window = [(start_date + timedelta(days=i)) for i in range(7)]
    cols = st.columns(7)
    
    for i, current_day in enumerate(days_in_window):
        date_str = current_day.strftime('%Y-%m-%d')
        display_date = current_day.strftime('%a, %b %d')
        
        with cols[i]:
            st.markdown(f"**{display_date}**")
            st.markdown("---")
            
            day_events = data[data['Date'] == date_str]
            
            if day_events.empty:
                st.info("No scheduled meetings.")
            else:
                day_events = day_events.sort_values(by='DateTime_Sort')
                grouped_events = day_events.groupby(['Committee', 'Time'], sort=False)
                
                for (committee, time_str), group_df in grouped_events:
                    with st.container(border=True):
                        st.markdown(f"🏛️ **{committee}**")
                        st.markdown(f"🕰️ *{time_str}*")
                        st.markdown("---")
                        
                        # FUTURE TAB LOGIC: Sort bills by their place on the Docket
                        if is_future:
                            group_df = group_df.sort_values(by='AgendaOrder')
                        
                        for _, row in group_df.iterrows():
                            st.markdown(f"**{row['Bill']}**")
                            
                            if is_future:
                                st.caption(f"📑 *Agenda Item #{int(row['AgendaOrder'])}*")
                            else:
                                st.caption(f"🔹 *Action:* {row['Outcome']}")
                            st.write("")

# ==========================================
# 5. THE DUAL-PAGE TOGGLE
# ==========================================
tab_past, tab_future = st.tabs([
    f"⏪ Past Week ({past_start.strftime('%b %d')} - {TODAY.strftime('%b %d')})", 
    f"⏩ Future Week ({(TODAY + timedelta(days=1)).strftime('%b %d')} - {future_end.strftime('%b %d')})"
])

with tab_past:
    render_kanban_week(past_start, TODAY - timedelta(days=1), clean_df, is_future=False)

with tab_future:
    render_kanban_week(TODAY, future_end, clean_df, is_future=True)
