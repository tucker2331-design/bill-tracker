import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
API_URL = "https://lis.virginia.gov/Committee/api/getCommitteesAsync"
SESSION_CODE = "20261" 
WEB_API_KEY = "FCE351B6-9BD8-46E0-B18F-5572F4CCA5B9"

st.set_page_config(page_title="v133 Directory Heist", page_icon="📂", layout="wide")
st.title("📂 v133: The Directory Heist")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://lis.virginia.gov/',
    'Webapikey': WEB_API_KEY # The key you found
}

def fetch_directory():
    st.write(f"🔐 **Authenticating with Master Key...**")
    
    params = {"sessionCode": SESSION_CODE}
    
    try:
        resp = session.get(API_URL, headers=HEADERS, params=params, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            st.success(f"✅ **ACCESS GRANTED!** Retrieved {len(data)} committees.")
            
            # PARSE
            committee_list = []
            for item in data:
                committee_list.append({
                    "Name": item.get("Name"),
                    "Integer ID": item.get("CommitteeId"), # THIS IS THE KEY
                    "Code": item.get("CommitteeCode"),     # e.g. H18
                    "Chamber": item.get("ChamberCode")
                })
            
            df = pd.DataFrame(committee_list)
            
            # 1. FIND PRIVILEGES
            st.divider()
            st.subheader("🎯 Target: Privileges & Elections")
            target = df[df["Name"].str.contains("Privileges", case=False, na=False)]
            
            if not target.empty:
                st.dataframe(target, use_container_width=True)
                
                # AUTOMATED SUBCOMMITTEE FETCH
                for index, row in target.iterrows():
                    secret_id = row['Integer ID']
                    name = row['Name']
                    
                    st.write(f"🔎 **Scanning Subcommittees for {name} (ID: {secret_id})...**")
                    
                    sub_url = "https://lis.virginia.gov/Committee/api/getCommitteeByIdAsync"
                    sub_params = {"sessionCode": SESSION_CODE, "id": str(secret_id)}
                    
                    sub_resp = session.get(sub_url, headers=HEADERS, params=sub_params)
                    if sub_resp.status_code == 200:
                        sub_data = sub_resp.json()
                        subs = sub_data.get("SubCommittees", [])
                        
                        if subs:
                            st.success(f"   -> Found {len(subs)} Subcommittees!")
                            
                            # GENERATE THE MAP
                            st.markdown("### 📋 FINAL COPY-PASTE MAP:")
                            code_block = "SUBCOMMITTEE_MAP = {\n"
                            for s in subs:
                                safe_name = s['Name'].replace("Subcommittee", "").replace("on", "").strip()
                                code_block += f'    "{safe_name}": "{s["CommitteeId"]}",\n'
                            code_block += "}"
                            st.code(code_block)
                            
                        else:
                            st.warning("   -> No subcommittees found.")
            else:
                st.error("Could not find 'Privileges' in the directory.")
                
            with st.expander("View Full Directory"):
                st.dataframe(df)
                
        else:
            st.error(f"❌ Failed ({resp.status_code})")
            
    except Exception as e:
        st.error(f"Error: {e}")

# --- UI ---
st.sidebar.header("📂 Directory Heist")
if st.sidebar.button("🔴 Download Master Directory"):
    fetch_directory()
