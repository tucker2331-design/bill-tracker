import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v600 Direct Inventory", page_icon="🗄️", layout="wide")
st.title("🗄️ v600: The 'Direct Inventory' Pivot")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def run_inventory():
    st.subheader("Step 1: Fetching Official Committee List...")
    
    # We found "Service: Committee" in your Heist. 
    # Standard naming suggests GetCommitteeListAsync.
    url = f"{API_BASE}/Committee/api/GetCommitteeListAsync"
    
    # Try House Committees first
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"}
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            if data:
                st.success(f"✅ Found {len(data)} Committees!")
                
                # Show the first few to verify we have REAL IDs now
                st.write("First 3 Committees found:")
                st.json(data[:3])
                
                # --- STEP 2: TRY TO INVENTORY THE FIRST ONE ---
                target_comm = data[0]
                comm_id = target_comm.get("CommitteeId")
                comm_name = target_comm.get("CommitteeName")
                
                if comm_id:
                    st.divider()
                    st.subheader(f"Step 2: Inventorying '{comm_name}' (ID: {comm_id})")
                    
                    # We try the Legislation service we saw in the Heist
                    # Legislation/api/GetLegislationByCommitteeAsync
                    bill_url = f"{API_BASE}/Legislation/api/GetLegislationByCommitteeAsync"
                    bill_params = {"sessionCode": SESSION_CODE, "committeeId": comm_id}
                    
                    r2 = session.get(bill_url, headers=headers, params=bill_params, timeout=5)
                    
                    if r2.status_code == 200:
                        bills = r2.json()
                        if bills:
                            st.success(f"🎉 **JACKPOT!** Found {len(bills)} bills in {comm_name}!")
                            st.json(bills[:5]) # Show first 5
                        else:
                            st.warning("⚠️ 200 OK (Empty List) - Committee exists but has no bills?")
                    elif r2.status_code == 404:
                        st.error("❌ 404: Endpoint Name Mismatch (We might need to fix the name)")
                    else:
                        st.error(f"❌ Status {r2.status_code}")
                else:
                    st.error("❌ Committee found, but ID is still NULL? This API is haunted.")
            else:
                st.warning("⚠️ 200 OK (Empty Committee List)")
        else:
            st.error(f"❌ Committee API Failed: {resp.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Inventory"):
    run_inventory()
