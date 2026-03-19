import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

st.set_page_config(page_title="Rolling Legislative Calendar", layout="wide")

st.title("📅 Rolling Legislative Calendar")
st.markdown("Dynamic 14-day tracking window with enterprise noise-filtering.")

# ==========================================
# 1. DYNAMIC TIME WINDOW CALCULATION
# ==========================================
# In production, this is just datetime.today()
# We hardcode to March 19, 2026, to match the current reality of the Virginia session
TODAY = datetime(2026, 3, 19)

past_start = TODAY - timedelta(days=7)
future_end = TODAY + timedelta(days=7)

# ==========================================
# 2. THE ENTERPRISE NOISE FILTER
# ==========================================
ACTIONABLE_VERBS = [
    'report', 'continue', 'pass', 'fail', 'incorporate', 
    'hearing', 'strike', 'stricken', 'veto', 'sign'
]

def apply_noise_filter(df):
    """Drops any CSV row that doesn't contain a strict legislative action verb."""
    if df.empty:
        return df
    # Create a regex pattern from our allowlist
    pattern = '|'.join(ACTIONABLE_VERBS)
    # Only keep rows where the Outcome matches an actionable verb (case-insensitive)
    filtered_df = df[df['Outcome'].str.contains(pattern, case=False, na=False)]
    return filtered_df

# ==========================================
# 3. MOCK ETL DATA (Simulating the final merge)
# ==========================================
raw_data = [
    # --- PAST WEEK ---
    {"Date": "2026-03-12", "Time": "10:00 AM", "Committee": "Courts of Justice", "Bill": "HB10", "Outcome": "Reported out of Courts of Justice (15-Y 0-N)"},
    {"Date": "2026-03-12", "Time": "10:30 AM", "Committee": "Courts of Justice", "Bill": "HB45", "Outcome": "Fiscal impact statement printed"}, # NOISE - Will be filtered
    {"Date": "2026-03-13", "Time": "08:00 AM", "Committee": "Finance", "Bill": "HB863", "Outcome": "Continued to 2027"},
    {"Date": "2026-03-14", "Time": "09:00 AM", "Committee": "Rules", "Bill": "SB4", "Outcome": "Passed by indefinitely in Rules (12-Y 4-N)"},
    {"Date": "2026-03-14", "Time": "11:00 AM", "Committee": "Appropriations", "Bill": "HB1204", "Outcome": "Incorporated into HB1100"},
    # --- FUTURE WEEK (Post-Sine Die) ---
    {"Date": "2026-03-24", "Time": "09:00 AM", "Committee": "Joint Commission", "Bill": "HB500", "Outcome": "Assigned to sub-committee"}, # NOISE - Will be filtered
    {"Date": "2026-03-25", "Time": "TBD", "Committee": "Governor's Desk", "Bill": "HB10", "Outcome": "Signed by Governor"}
]

df = pd.DataFrame(raw_data)
# Convert time to datetime objects for accurate chronological sorting
df['DateTime_Sort'] = pd.to_datetime(df['Date'] + ' ' + df['Time'].replace('TBD', '11:59 PM'), errors='coerce')

# Apply the Allowlist Filter!
clean_df = apply_noise_filter(df)

# ==========================================
# 4. THE UI RENDER ENGINE (KANBAN LAYOUT)
# ==========================================
def render_kanban_week(start_date, end_date, data):
    """Generates the horizontal day columns and vertical event cards."""
    
    # Generate a list of the 7 days in this window
    days_in_window = [(start_date + timedelta(days=i)) for i in range(7)]
    
    # Create 7 Streamlit columns
    cols = st.columns(7)
    
    for i, current_day in enumerate(days_in_window):
        date_str = current_day.strftime('%Y-%m-%d')
        display_date = current_day.strftime('%a, %b %d')
        
        with cols[i]:
            # Day Header
            st.markdown(f"**{display_date}**")
            st.markdown("---")
            
            # Filter the master dataframe for just this specific day
            day_events = data[data['Date'] == date_str]
            
            if day_events.empty:
                st.info("No scheduled meetings.")
            else:
                # Sort chronologically
                day_events = day_events.sort_values(by='DateTime_Sort')
                
                # Draw the vertical event cards
                for _, row in day_events.iterrows():
                    with st.container(border=True):
                        st.markdown(f"🕰️ **{row['Time']}** | **{row['Bill']}**")
                        st.markdown(f"🏛️ *{row['Committee']}*")
                        st.caption(f"↳ {row['Outcome']}")

# ==========================================
# 5. THE DUAL-PAGE TOGGLE
# ==========================================
tab_past, tab_future = st.tabs([
    f"⏪ Past Week ({past_start.strftime('%b %d')} - {TODAY.strftime('%b %d')})", 
    f"⏩ Future Week ({(TODAY + timedelta(days=1)).strftime('%b %d')} - {future_end.strftime('%b %d')})"
])

with tab_past:
    render_kanban_week(past_start, TODAY - timedelta(days=1), clean_df)

with tab_future:
    render_kanban_week(TODAY, future_end, clean_df)
