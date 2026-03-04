import streamlit as st
import requests

st.set_page_config(page_title="Deep Dive Probe", layout="wide")
st.title("🔓 LIS Database: The Vault Breach")
st.markdown("Executing the two-step relational join to bypass the directory and access the raw bill payload...")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

# STEP 1: The Directory (Get the Keys)
URL_1 = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"
PARAMS_1 = {"sessionCode": "20261", "chamberCode": "S", "committeeNumber": "S15"} # Senate Finance

with st.spinner("Step 1: Pinging Directory for Vault Keys..."):
    try:
        resp_1 = requests.get(URL_1, headers=HEADERS, params=PARAMS_1, timeout=10)
        if resp_1.status_code == 200:
            data_1 = resp_1.json()
            items = data_1.get("ListItems", [])
            
            if items:
                # Grab the keys from the first available meeting
                target_meeting = items[0]
                docket_id = target_meeting.get("DocketID")
                ref_num = target_meeting.get("ReferenceNumber")
                
                st.success(f"Keys Acquired! DocketID: `{docket_id}` | ReferenceNumber: `{ref_num}`")
                
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
                st.warning("Directory returned empty. No upcoming Senate Finance meetings found.")
        else:
            st.error(f"Directory Error: Status {resp_1.status_code}")
    except Exception as e:
        st.error(f"Network error: {e}")
