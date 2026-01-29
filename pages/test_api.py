import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
# We confirmed this in v803
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v900 Reverse Engineer", page_icon="🔭", layout="wide")
st.title("🔭 v900: The Reverse-Engineer (Wide Search)")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_reverse_engineer():
    st.subheader(f"Step 1: Fetching ALL House Bills for Session {SESSION_CODE}...")
    st.info("Removing Committee filters to see what raw data looks like.")
    
    search_url = f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync"
    
    # PAYLOAD: Broadest possible search (Just Session + Chamber)
    payload = {
        "SessionCode": SESSION_CODE,
        "ChamberCode": "H"
        # "CommitteeId": REMOVED - Let's see everything
    }
    
    st.write(f"🚀 POSTing Broad Search...", payload)
    
    try:
        resp = session.post(search_url, headers=headers, json=payload, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            
            # Unwrap Logic
            bills = []
            if isinstance(data, dict):
                 if "Legislation" in data: bills = data["Legislation"]
                 elif "Items" in data: bills = data["Items"]
                 elif "Results" in data: bills = data["Results"]
            elif isinstance(data, list):
                bills = data
            
            if bills:
                st.success(f"🎉 **SUCCESS!** Downloaded {len(bills)} House Bills.")
                
                # --- STEP 2: INSPECT THE COMMITTEE FORMAT ---
                st.divider()
                st.subheader("Step 2: Inspecting Committee Data")
                st.write("We need to see how the API *actually* stores committee info.")
                
                # Find a bill that is actually IN a committee
                assigned_bill = next((b for b in bills if b.get("CommitteeId") or b.get("CommitteeName")), None)
                
                if assigned_bill:
                    st.write(f"found Bill: **{assigned_bill.get('LegislationNumber')}**")
                    st.json(assigned_bill)
                    
                    # Highlight the keys we care about
                    c_id = assigned_bill.get("CommitteeId")
                    c_num = assigned_bill.get("CommitteeNumber")
                    c_name = assigned_bill.get("CommitteeName")
                    
                    st.info(f"💡 **THE ANSWER KEY:**")
                    st.code(f"CommitteeId: {c_id} (Type: {type(c_id)})\nCommitteeNumber: {c_num}\nCommitteeName: {c_name}")
                else:
                    st.warning("Found bills, but none seem to have committee assignments yet? (Maybe they are all 'Introduced')")
                    st.json(bills[:3])
            else:
                st.warning("⚠️ 200 OK (Empty List). Session 20261 might be valid but have no House bills yet?")
                
        else:
            st.error(f"❌ Search Failed: {resp.status_code}")
            st.text(resp.text[:500])

    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Reverse Engineer"):
    run_reverse_engineer()
