import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
SESSION_CODE = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v601 Data Un-Wrapper", page_icon="🎁", layout="wide")
st.title("🎁 v601: The Data Un-Wrapper")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'WebAPIKey': API_KEY
}

def run_inventory_fix():
    st.subheader("Step 1: Fetching Official Committee List...")
    
    url = f"{API_BASE}/Committee/api/GetCommitteeListAsync"
    params = {"sessionCode": SESSION_CODE, "chamberCode": "H"}
    
    try:
        resp = session.get(url, headers=headers, params=params, timeout=5)
        
        if resp.status_code == 200:
            raw_data = resp.json()
            
            # --- THE FIX: Handle Wrappers ---
            committees = []
            if isinstance(raw_data, list):
                committees = raw_data
            elif isinstance(raw_data, dict):
                # Try to find the list inside the dict
                keys = list(raw_data.keys())
                st.info(f"📦 Response is a Wrapper. Keys found: {keys}")
                
                # Guess common wrapper names based on previous patterns
                if "Committees" in raw_data: committees = raw_data["Committees"]
                elif "Items" in raw_data: committees = raw_data["Items"]
                elif "Data" in raw_data: committees = raw_data["Data"]
                else:
                    # Fallback: Grab the first value if it's a list
                    for k in keys:
                        if isinstance(raw_data[k], list):
                            committees = raw_data[k]
                            break
            
            if committees:
                st.success(f"✅ Unwrap Successful! Found {len(committees)} Committees.")
                
                # Show the first valid committee to verify IDs
                target = committees[0]
                st.write("🔎 **Committee Data Structure:**")
                st.json(target)
                
                # --- STEP 2: INVENTORY ---
                # Now we grab the REAL ID from this verified object
                # It might be 'CommitteeId', 'Id', 'Code', etc.
                c_id = target.get("CommitteeId") or target.get("Id")
                c_name = target.get("CommitteeName") or target.get("Name")
                
                if c_id:
                    st.divider()
                    st.subheader(f"Step 2: Checking Bills for '{c_name}' (ID: {c_id})")
                    
                    bill_url = f"{API_BASE}/Legislation/api/GetLegislationByCommitteeAsync"
                    bill_params = {"sessionCode": SESSION_CODE, "committeeId": c_id}
                    
                    r2 = session.get(bill_url, headers=headers, params=bill_params, timeout=5)
                    
                    if r2.status_code == 200:
                        bills = r2.json()
                        # Handle Wrapper for Bills too just in case
                        if isinstance(bills, dict):
                            st.info(f"📦 Bill Response Keys: {list(bills.keys())}")
                            # Try to extract list
                            if "Legislation" in bills: bills = bills["Legislation"]
                            elif "Items" in bills: bills = bills["Items"]
                        
                        if bills:
                            st.success(f"🎉 **PAYDIRT!** Found {len(bills)} bills!")
                            st.dataframe(bills) # Show the data
                        else:
                            st.warning("⚠️ 200 OK (Empty Bill List)")
                    else:
                        st.error(f"❌ Bill Fetch Failed: {r2.status_code}")
                else:
                    st.error("❌ Could not find an 'ID' field in the committee object.")
            else:
                st.error("❌ Failed to extract a list from the response.")
                st.write("Raw Dump:", raw_data)
                
        else:
            st.error(f"❌ API Failed: {resp.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Un-Wrapper"):
    run_inventory_fix()
