import streamlit as st
import requests

st.set_page_config(page_title="Brute Force Probe", layout="wide")
st.title("🔓 LIS Database: The Brute-Force Vault Breach")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}
URL_1 = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"
URL_2 = "https://lis.virginia.gov/Calendar/api/getdocketsbyidasync"

with st.spinner("Brute-forcing 50+ committee codes to find an active payload..."):
    found = False
    # Try both House (H) and Senate (S) committees from 01 to 25
    chambers = ["H", "S"]
    
    for chamber in chambers:
        if found: break
        for i in range(1, 26):
            comm_code = f"{chamber}{i:02d}" # Generates H01, H02, S01, etc.
            params_1 = {"sessionCode": "20261", "chamberCode": chamber, "committeeNumber": comm_code}
            
            try:
                r1 = requests.get(URL_1, headers=HEADERS, params=params_1, timeout=5)
                if r1.status_code == 200:
                    data_1 = r1.json()
                    items = data_1.get("ListItems", [])
                    if items:
                        docket_id = items[0].get("DocketID")
                        ref_num = items[0].get("ReferenceNumber")
                        
                        st.success(f"Hit! Committee `{comm_code}` is active. DocketID: `{docket_id}` | RefNum: `{ref_num}`")
                        
                        # STEP 2: The Vault
                        params_2 = {"docketId": str(docket_id), "referenceNumber": str(ref_num)}
                        r2 = requests.get(URL_2, headers=HEADERS, params=params_2, timeout=5)
                        
                        if r2.status_code == 200:
                            st.success("Vault breached! Here is the payload schema:")
                            st.json(r2.json())
                            found = True
                            break
            except Exception:
                pass # Ignore network hiccups and keep scanning
                
    if not found:
        st.error("Exhausted all 50 committees. The entire docket database for this session appears to be cleared or inactive.")
