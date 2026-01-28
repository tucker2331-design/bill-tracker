ximport streamlit as st
import requests
from datetime import datetime

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v504 Real Committee Hunter", page_icon="🦁", layout="wide")
st.title("🦁 v504: The 'Real Committee' Hunter")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def probe_real_committees():
    st.subheader("Step 1: Scanning Schedule for VALID Committees...")
    
    url = f"{API_BASE}/Schedule/api/getschedulelistasync"
    # We check both chambers to ensure we find a valid target
    
    valid_targets = []
    
    try:
        # Check House & Senate
        for chamber in ["H", "S"]:
            params = {"sessionCode": SESSION_CODE, "chamberCode": chamber}
            resp = session.get(url, headers=headers, params=params, timeout=5)
            if resp.status_code == 200:
                events = resp.json().get("Schedules", [])
                today_str = datetime.now().strftime("%Y-%m-%d")
                
                for e in events:
                    # FILTER 1: Must be in the future
                    if e.get("ScheduleDate", "") < today_str: continue
                    # FILTER 2: Must NOT be cancelled
                    if e.get("IsCancelled"): continue
                    # FILTER 3 (THE FIX): Must have a valid CommitteeId (Not a Caucus)
                    if not e.get("CommitteeId"): continue
                    
                    valid_targets.append(e)

        if not valid_targets:
            st.error("❌ No valid standing committee meetings found in the near future.")
            return

        # Sort by date
        valid_targets.sort(key=lambda x: x.get("ScheduleDate"))
        
        # Pick the best candidate
        target = valid_targets[0]
        
        st.success(f"✅ Locked on LEGISLATIVE Target: **{target.get('OwnerName')}**")
        st.info(f"📅 Date: {target.get('ScheduleDate')} | 🆔 CommitteeId: {target.get('CommitteeId')}")
        
        # --- STEP 2: THE BRIDGE TEST ---
        st.divider()
        st.subheader("🧪 Testing the Bridge")
        
        # Now we use the ID we KNOW exists
        schedule_id = target.get("ScheduleId")
        committee_id = target.get("CommitteeId")
        
        st.write(f"Attempting to fetch docket for **Schedule ID: {schedule_id}**...")
        
        docket_url = f"{API_BASE}/Calendar/api/GetDocketListAsync"
        
        # Try Strategy A: Schedule ID
        r = session.get(docket_url, headers=headers, params={"sessionCode": SESSION_CODE, "scheduleId": schedule_id}, timeout=5)
        
        if r.status_code == 200:
            data = r.json()
            if data:
                st.success(f"🎉 **PAYDIRT!** Found {len(data)} bills on the docket!")
                st.dataframe(data) # Show the actual data structure
                st.balloons()
            else:
                st.warning("⚠️ Status 200 (Empty List). The meeting is valid, but no bills are listed yet.")
                
        elif r.status_code == 204:
            st.info("⚪ Status 204: Valid meeting, but docket is currently empty.")
            
            # Fallback: Try Committee ID inventory
            st.write("Trying backup: Fetching full Committee Inventory...")
            inv_url = f"{API_BASE}/Legislation/api/GetLegislationByCommitteeAsync"
            r2 = session.get(inv_url, headers=headers, params={"sessionCode": SESSION_CODE, "committeeId": committee_id}, timeout=5)
            if r2.status_code == 200 and r2.json():
                st.success(f"✅ Backup Successful: Found {len(r2.json())} bills in this committee.")
                st.json(r2.json()[:3]) # Show first 3
            
        else:
            st.error(f"❌ Status {r.status_code}")

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Hunter"):
    probe_real_committees()
