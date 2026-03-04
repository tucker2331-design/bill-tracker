import streamlit as st
import requests

st.set_page_config(page_title="Wide-Net Probe", layout="wide")
st.title("🔓 LIS Database: The Wide-Net Vault Breach")
st.markdown("Bypassing empty committees to find ANY available Senate payload...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# STEP 1: The Wide Net (Get ALL Dockets for the session)
URL_1 = "https://lis.virginia.gov/Calendar/api/getdocketlistasync"
PARAMS_1 = {"sessionCode": "20261"} 

with st.spinner("Step 1: Pinging Directory for ANY available Docket Keys..."):
    try:
        resp_1 = requests.get(URL_1, headers=HEADERS, params=PARAMS_1, timeout=10)
        
        if resp_1.status_code == 200:
            data_1 = resp_1.json()
            items = data_1.get("ListItems", [])
            
            # Filter for the first available Senate docket
            senate_dockets = [i for i in items if i.get("ChamberCode") == "S"]
            
            if senate_dockets:
                target_meeting = senate_dockets[0]
                docket_id = target_meeting.get("DocketID")
                ref_num = target_meeting.get("ReferenceNumber")
                comm_name = target_meeting.get("CommitteeName", "Unknown Committee")
                
                st.success(f"Keys Acquired for {comm_name}! DocketID: `{docket_id}` | ReferenceNumber: `{ref_num}`")
                
                # STEP 2: The Vault (Get the Bills)
                st.info("Step 2: Unlocking the Payload Endpoint...")
                URL_2 = "https://lis.virginia.gov/Calendar/api/getdocketsbyidasync"
                PARAMS_2 = {"docketId": str(docket_id), "referenceNumber": str(ref_num)}
                
                resp_2 = requests.get(URL_2, headers=HEADERS, params=PARAMS_2, timeout=10)
                if resp_2.status_code == 200:
                    st.success("Vault breached. Here is the true payload:")
                    st.json(resp_2.json())
                else:
                    st.error(f"Vault Rejected the keys: Status {resp_2.status_code}")
            else:
                st.warning("Directory returned data, but zero Senate meetings were found.")
                st.json(data_1) # Show what we DID find
                
        elif resp_1.status_code == 204:
            st.error("Status 204: The ENTIRE docket database is currently empty. The session may be over.")
        else:
            st.error(f"Directory Error: Status {resp_1.status_code}")
            
    except Exception as e:
        st.error(f"Network error: {e}")
