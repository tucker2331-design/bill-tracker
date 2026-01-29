import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v602 Case Sensitive Fix", page_icon="🔑", layout="wide")
st.title("🔑 v602: The Case-Sensitive Fix")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def run_inventory_v602():
    st.subheader("Step 1: Fetching Official Committee List...")
    
    url = f"{API_BASE}/Committee/api/GetCommitteeListAsync"
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"}
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            raw_data = resp.json()
            committees = []
            
            # UNWRAP (As seen in your screenshot)
            if isinstance(raw_data, dict) and "Committees" in raw_data:
                committees = raw_data["Committees"]
            
            if committees:
                st.success(f"✅ Found {len(committees)} Committees.")
                
                # --- STEP 2: INVENTORY ---
                target = committees[0]
                
                # THE FIX: Use "CommitteeID" (capital D) as seen in screenshot
                c_id = target.get("CommitteeID") 
                c_name = target.get("Name")
                
                st.info(f"🎯 Target: **{c_name}** | Internal ID: `{c_id}`")
                
                if c_id:
                    st.divider()
                    st.subheader(f"Step 2: Fetching Bills for Committee {c_id}")
                    
                    # We try the endpoint from your valid list:
                    # Legislation/api/GetLegislationByCommitteeAsync
                    bill_url = f"{API_BASE}/Legislation/api/GetLegislationByCommitteeAsync"
                    
                    # We send the ID as "committeeId" (standard param casing)
                    bill_params = {"sessionCode": SESSION_CODE, "committeeId": c_id}
                    
                    st.write(f"🚀 Requesting: `{bill_url}` with ID `{c_id}`")
                    r2 = session.get(bill_url, headers=headers, params=bill_params, timeout=5)
                    
                    if r2.status_code == 200:
                        bill_data = r2.json()
                        
                        # Handle Wrapper (likely "Legislation" or "Items")
                        real_bills = []
                        if isinstance(bill_data, list):
                            real_bills = bill_data
                        elif isinstance(bill_data, dict):
                             # Dump keys to help debug if wrapper name is weird
                            st.caption(f"📦 Wrapper Keys: {list(bill_data.keys())}")
                            if "Legislation" in bill_data: real_bills = bill_data["Legislation"]
                            elif "Items" in bill_data: real_bills = bill_data["Items"]
                            elif "Committees" in bill_data: real_bills = bill_data["Committees"] # Unlikely but possible copy/paste
                        
                        if real_bills:
                            st.success(f"🎉 **PROOF OF LOGIC!** Found {len(real_bills)} bills!")
                            st.dataframe(real_bills[:10]) # Show first 10
                            st.balloons()
                        else:
                            st.warning("⚠️ 200 OK (Empty List). Committee exists, but has no bills assigned yet?")
                            st.json(bill_data) # Show raw just in case
                            
                    elif r2.status_code == 404:
                         # Fallback: Maybe the endpoint name is slightly different?
                         st.error("❌ 404 Not Found. Trying Backup Endpoint...")
                         backup_url = f"{API_BASE}/CommitteeLegislation/api/GetCommitteeLegislationListAsync"
                         r3 = session.get(backup_url, headers=headers, params=bill_params, timeout=5)
                         if r3.status_code == 200:
                             st.success("✅ BACKUP WORKED!")
                             st.json(r3.json())
                         else:
                             st.error(f"❌ Backup Failed: {r3.status_code}")
                    else:
                        st.error(f"❌ Bill Fetch Failed: {r2.status_code}")
                else:
                    st.error("❌ Still can't find ID. Check JSON below:")
                    st.json(target)
            else:
                st.error("❌ Failed to unwrap 'Committees' list.")
                
        else:
            st.error(f"❌ Committee API Failed: {resp.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run v602"):
    run_inventory_v602()
