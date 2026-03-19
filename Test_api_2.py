import streamlit as st
import requests

st.set_page_config(page_title="API Master Key", layout="wide")
st.title("🗝️ Enterprise LIS Master Key Probe")

API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984"
HEADERS = {"WebAPIKey": API_KEY, "Accept": "application/json"}

tab1, tab2, tab3 = st.tabs(["🕰️ Time-Travel Test (Rule out Empty Data)", "🧬 The Session ID Hunter", "💉 The GUID Injector Test"])

# --- TAB 1: THE TIME TRAVEL TEST ---
with tab1:
    st.subheader("Did it fail because 2026 is empty?")
    st.write("We will ping the exact same endpoint, but ask for the **20251** and **20241** sessions. If these return 200 OK, it means our code is perfect and the API simply crashes when a future docket is empty.")
    
    if st.button("🚀 Fire Time-Travel Probe"):
        target_url = "https://lis.virginia.gov/Calendar/api/getdocketlistbycommitteenumberasync"
        
        for year in ["20251", "20241"]:
            params = {"sessionCode": year, "chamberCode": "H", "committeeNumber": "02"}
            res = requests.get(target_url, headers=HEADERS, params=params)
            if res.status_code == 200:
                st.success(f"✅ **{year} SUCCESS!** The endpoint works. 2026 is just empty/crashing on the state's end.")
                st.json(res.json())
                break
            else:
                st.error(f"❌ {year} Failed: {res.status_code}")

# --- TAB 2: THE SESSION ID HUNTER ---
with tab2:
    st.subheader("Hunting the Hidden GUID")
    st.write("If the API secretly requires a `sessionID` string, we have to find it. We will ping the root Session list to extract the master keys.")
    
    if st.button("🧬 Hunt Session IDs"):
        # Testing the two most common naming conventions for root session endpoints
        urls_to_test = [
            "https://lis.virginia.gov/Session/api/getsessionlistasync",
            "https://lis.virginia.gov/Session/api/getsessionsasync"
        ]
        
        found = False
        for url in urls_to_test:
            res = requests.get(url, headers=HEADERS)
            if res.status_code == 200:
                st.success("✅ Root Session List Found!")
                st.json(res.json())
                found = True
                break
        
        if not found:
            st.error("❌ Could not locate the root session endpoint. Check Postman's 'Session' folder for the exact URL.")

# --- TAB 3: THE GUID INJECTOR ---
with tab3:
    st.subheader("Injecting the GUID")
    st.write("If you found a massive `sessionID` string (e.g., 'a1b2c3d4...') in Postman or Tab 2, paste it here to inject it into the payload.")
    
    guid_input = st.text_input("Paste sessionID GUID here:")
    
    if st.button("💉 Fire Injected Payload"):
        if not guid_input:
            st.warning("Please paste a GUID first.")
        else:
            # We hit the main docket endpoint that explicitly asks for sessionID
            url = "https://lis.virginia.gov/Calendar/api/getdocketlistasync"
            params = {
                "sessionID": guid_input.strip(),
                "chamberCode": "H",
                "committeeID": "H02",
                "sessionCode": "20261"
            }
            
            res = requests.get(url, headers=HEADERS, params=params)
            if res.status_code == 200:
                st.success("✅ **LOCK CRACKED!** The sessionID GUID was the missing key.")
                st.json(res.json())
            else:
                st.error(f"❌ Failed. Status: {res.status_code} | Params sent: {params}")
