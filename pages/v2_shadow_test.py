import streamlit as st
import requests

st.set_page_config(page_title="Time Machine Probe", layout="wide")
st.title("🔓 LIS Database: The Time Machine Breach")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
URL_1 = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"
URL_2 = "https://lis.virginia.gov/Calendar/api/getdocketsbyidasync"

with st.spinner("Accessing 2025 historical records to find a payload schema..."):
    found = False
    chambers = ["H", "S"]
    
    for chamber in chambers:
        if found: break
        for i in range(1, 26):
            comm_code = f"{chamber}{i:02d}" 
            # THE BYPASS: Using 20251 instead of 20261
            params_1 = {"sessionCode": "20251", "chamberCode": chamber, "committeeNumber": comm_code}
            
            try:
                r1 = requests.get(URL_1, headers=HEADERS, params=params_1, timeout=5)
                if r1.status_code == 200:
                    data_1 = r1.json()
                    items = data_1.get("ListItems", [])
                    if items:
                        docket_id = items[0].get("DocketID")
                        ref_num = items[0].get("ReferenceNumber")
                        
                        st.success(f"Hit! Historical 2025 Committee `{comm_code}` found. DocketID: `{docket_id}`")
                        
                        # STEP 2: The Vault
                        params_2 = {"docketId": str(docket_id), "referenceNumber": str(ref_num)}
                        r2 = requests.get(URL_2, headers=HEADERS, params=params_2, timeout=5)
                        
                        if r2.status_code == 200:
                            st.success("Historical vault breached! Here is the payload schema:")
                            st.json(r2.json())
                            found = True
                            break
            except Exception:
                pass 
                
    if not found:
        st.error("Historical database failed to return records.")
