import streamlit as st
import requests
import pandas as pd

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
API_URL = "https://lis.virginia.gov/Committee/api/getCommitteesAsync"
SESSION_CODE = "20261" 

st.set_page_config(page_title="v128 Cookie Jar", page_icon="🍪", layout="wide")
st.title("🍪 v128: The Cookie Jar (Session Priming)")

# --- NETWORK ENGINE ---
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=2)
session.mount('https://', adapter)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://lis.virginia.gov/session-details/20261/committee-information/H18/committee-details'
}

def fetch_master_list():
    status_log = st.empty()
    
    # STEP 1: VISIT FRONT DESK (Get Cookies)
    status_log.info("🍪 Step 1: Visiting Homepage to get Cookies...")
    try:
        # We visit the actual page a human would start at
        front_desk = f"{BASE_URL}/session-details/{SESSION_CODE}/committee-information/H18/committee-details"
        session.get(front_desk, headers=HEADERS, timeout=5)
        cookies = session.cookies.get_dict()
        if cookies:
            st.success(f"✅ Got {len(cookies)} Cookies!")
        else:
            st.warning("⚠️ No cookies received (might still work).")
            
    except Exception as e:
        st.error(f"Front Desk Error: {e}")
        return

    # STEP 2: REQUEST MASTER LIST
    status_log.info("📂 Step 2: Downloading Master Committee List...")
    params = {"sessionCode": SESSION_CODE}
    
    try:
        resp = session.get(API_URL, headers=HEADERS, params=params, cookies=session.cookies, timeout=5)
        
        if resp.status_code == 200:
            status_log.success("✅ ACCESS GRANTED!")
            data = resp.json()
            
            # PARSE RESULTS
            committee_list = []
            for item in data:
                # We are looking for the PARENT committees (Chambers) to find the ID
                committee_list.append({
                    "Name": item.get("Name"),
                    "Integer ID": item.get("CommitteeId"), # THIS IS IT
                    "Code": item.get("CommitteeCode"), # e.g. H18
                    "Chamber": item.get("ChamberCode")
                })
            
            # DISPLAY
            df = pd.DataFrame(committee_list)
            
            # Highlight our target
            st.subheader("🎯 Target Identified:")
            target = df[df["Name"].str.contains("Privileges", case=False, na=False)]
            if not target.empty:
                st.dataframe(target, use_container_width=True)
                st.success(f"The Secret ID for Privileges & Elections is: **{target.iloc[0]['Integer ID']}**")
                
                st.divider()
                st.write("**Next Step:**")
                st.write(f"Go back to the 'Integer Hunt' tool and enter **{target.iloc[0]['Integer ID']}** to see the subcommittees!")
            else:
                st.warning("Could not find 'Privileges' in the list. Search below:")
            
            with st.expander("View Full Master List"):
                st.dataframe(df)
                
        elif resp.status_code == 401:
            status_log.error("❌ 401 Unauthorized. The cookies didn't stick.")
        else:
            status_log.error(f"❌ Error {resp.status_code}")
            
    except Exception as e:
        st.error(f"API Error: {e}")

# --- UI ---
st.sidebar.header("🍪 Cookie Jar")
if st.sidebar.button("🔴 Fetch Master List"):
    fetch_master_list()
