import streamlit as st
import requests
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = 20261 

st.set_page_config(page_title="v6 Endpoint War", page_icon="⚔️", layout="wide")
st.title("⚔️ v6: Battle of the Endpoints")

def inspect_endpoint(name, url):
    """Pings an endpoint and checks its Date Horizon"""
    headers = {"WebAPIKey": API_KEY, "Accept": "application/json"}
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"} # Testing House
    
    st.subheader(f"📡 Testing: `{name}`")
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            # The key name changes based on endpoint
            # Schedule -> "Schedules", Committee -> "CommitteeMeetings"
            items = data.get("Schedules") or data.get("CommitteeMeetings") or []
            
            if not items:
                st.warning("⚠️ No items returned.")
                return

            st.success(f"✅ Downloaded {len(items)} items.")
            
            # --- DATE FORENSICS ---
            dates = []
            for item in items:
                # Try every possible date key
                d_str = item.get("ScheduleDate") or item.get("MeetingDate") or item.get("Date")
                if d_str:
                    try:
                        # Clean "T" format
                        d_clean = d_str.split("T")[0]
                        dates.append(d_clean)
                    except: pass
            
            dates.sort()
            if dates:
                st.info(f"🗓️ Date Range: **{dates[0]}** to **{dates[-1]}**")
                
                # CHECK FUTURE
                today = datetime.now().strftime("%Y-%m-%d")
                future_dates = [d for d in dates if d > today]
                
                if future_dates:
                    st.balloons()
                    st.success(f"🔥 FOUND FUTURE DATA! ({len(future_dates)} meetings)")
                    st.write("First 5 Future Dates found:", future_dates[:5])
                    
                    # Inspect one future item to see if it has the LINK
                    st.markdown("**Example Future Meeting Data:**")
                    # Find the object that matches the first future date
                    for item in items:
                        d_str = item.get("ScheduleDate") or item.get("MeetingDate")
                        if d_str and d_str.split("T")[0] == future_dates[0]:
                            st.json(item)
                            break
                else:
                    st.error("❌ NO Future Data found (Max date is Today or Past).")
            else:
                st.warning("Could not parse any dates.")
                
        else:
            st.error(f"❌ API Error: {resp.status_code}")
            
    except Exception as e:
        st.error(f"💥 Connection Error: {e}")

if st.button("🚀 Run Comparison"):
    
    col1, col2 = st.columns(2)
    
    with col1:
        # TEST 1: The one we used before (likely failing)
        inspect_endpoint("Schedule List", "https://lis.virginia.gov/Schedule/api/getschedulelistasync")
        
    with col2:
        # TEST 2: The New Hope (Committee Meetings)
        inspect_endpoint("Committee Meetings", "https://lis.virginia.gov/Committee/api/getcommitteemeetinglistasync")
