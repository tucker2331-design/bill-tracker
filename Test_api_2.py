import streamlit as st
import requests

st.set_page_config(page_title="Naked API Diagnostic")
st.title("🔍 Naked URL Diagnostic")
st.markdown("Pinging the Virginia servers directly to find the exact endpoints.")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

if st.button("🚀 Fire Diagnostic Probes"):
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Testing Azure Blob CSVs")
        
        # Test 1: The lisfiles container with 20261
        url1 = "https://lis.blob.core.windows.net/lisfiles/20261/HISTORY.CSV"
        res1 = requests.get(url1)
        st.write(f"URL: `.../lisfiles/20261/HISTORY.CSV`")
        if res1.status_code == 200 and "<?xml" not in res1.text[:20]:
            st.success("✅ 200 OK (Valid CSV Data)")
        else:
            st.error(f"❌ Failed (Status: {res1.status_code} or XML Error)")

        # Test 2: The lisfiles container with 261
        url2 = "https://lis.blob.core.windows.net/lisfiles/261/HISTORY.CSV"
        res2 = requests.get(url2)
        st.write(f"URL: `.../lisfiles/261/HISTORY.CSV`")
        if res2.status_code == 200 and "<?xml" not in res2.text[:20]:
            st.success("✅ 200 OK (Valid CSV Data)")
        else:
            st.error(f"❌ Failed (Status: {res2.status_code} or XML Error)")
            
    with col2:
        st.subheader("2. Testing Schedule JSON API")
        
        # Test 3: API with 261
        url3 = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
        res3 = requests.get(url3, headers=HEADERS, params={"sessionCode": "261"})
        st.write(f"URL: `Schedule API + sessionCode=261`")
        if res3.status_code == 200 and len(res3.text) > 50:
            st.success("✅ 200 OK (Valid JSON Data)")
        else:
            st.error(f"❌ Failed (Status: {res3.status_code})")

        # Test 4: API with 20261
        url4 = "https://lis.virginia.gov/Schedule/api/getschedulelistasync"
        res4 = requests.get(url4, headers=HEADERS, params={"sessionCode": "20261"})
        st.write(f"URL: `Schedule API + sessionCode=20261`")
        if res4.status_code == 200 and len(res4.text) > 50:
            st.success("✅ 200 OK (Valid JSON Data)")
        else:
            st.error(f"❌ Failed (Status: {res4.status_code})")
            
        # Test 5: The Session API (To find the future session codes)
        st.markdown("---")
        st.subheader("3. Session Bucket API")
        url5 = "https://lis.virginia.gov/Session/api/getsessionlistasync"
        res5 = requests.get(url5, headers=HEADERS)
        st.write(f"URL: `Session API`")
        if res5.status_code == 200:
            st.success("✅ 200 OK")
            sessions = res5.json()
            st.write("Available Session Codes found on the server right now:")
            for s in sessions:
                # Print the display name and the code we need to use
                st.code(f"Name: {s.get('DisplayName')} | Code: {s.get('SessionCode')}")
        else:
            st.error(f"❌ Failed (Status: {res5.status_code})")
