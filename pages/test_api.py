import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525 # Known ID for HB1

st.set_page_config(page_title="v1001 Version Crawler", page_icon="🕷️", layout="wide")
st.title("🕷️ v1001: The 'Version' Crawler & POST Fix")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_crawler():
    # --- PART 1: FIXING THE HISTORY PROBE (POST) ---
    st.subheader(f"Step 1: History Check for HB1 (ID: {HB1_ID})...")
    hist_url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
    
    # FIX: Send as POST with JSON body
    payload = {"LegislationId": HB1_ID, "SessionCode": SESSION_CODE}
    
    try:
        r = session.post(hist_url, headers=headers, json=payload, timeout=5)
        
        if r.status_code == 200:
            history = r.json()
            if history:
                st.success(f"✅ History Unlocked! ({len(history)} items)")
                st.dataframe(history)
            else:
                st.warning("⚠️ 200 OK (Empty History).")
        else:
            # Try 'legislationId' lowercase key if TitleCase fails
            r2 = session.post(hist_url, headers=headers, json={"legislationId": HB1_ID, "sessionCode": SESSION_CODE}, timeout=5)
            if r2.status_code == 200:
                 st.success("✅ History Unlocked (Lowercase Params)!")
                 st.dataframe(r2.json())
            else:
                 st.error(f"❌ History Failed: {r.status_code} / {r2.status_code}")
    except Exception as e:
        st.error(f"Error: {e}")

    # --- PART 2: THE BILL CRAWLER (HB1 - HB10) ---
    st.divider()
    st.subheader("Step 2: Crawling HB1 - HB10...")
    
    # We use the endpoint PROVEN to work in v801
    ver_url = f"{API_BASE}/LegislationVersion/api/GetLegislationVersionByBillNumberAsync"
    
    found_bills = []
    
    # Scan first 5 bills
    progress_bar = st.progress(0)
    
    for i in range(1, 6): # HB1 to HB5
        b_num = f"HB{i}"
        
        # This endpoint uses GET params (proven in screenshot)
        params = {"sessionCode": SESSION_CODE, "billNumber": b_num}
        
        try:
            r = session.get(ver_url, headers=headers, params=params, timeout=2)
            if r.status_code == 200:
                data = r.json()
                # Unwrap list
                if isinstance(data, dict) and "LegislationsVersion" in data: items = data["LegislationsVersion"]
                elif isinstance(data, list): items = data
                else: items = []
                
                if items:
                    # Get the most recent version
                    latest = items[0]
                    found_bills.append({
                        "Bill": b_num,
                        "ID": latest.get("LegislationID"),
                        "Title": latest.get("Description"),
                        "Status": latest.get("Version")
                    })
        except:
            pass
        progress_bar.progress(i * 20)
        
    if found_bills:
        st.success(f"🎉 **CRAWLER SUCCESS!** Found {len(found_bills)} bills.")
        st.table(found_bills)
        st.info("💡 If this works, we don't need the 'Master List'. We can just crawl the numbers.")
    else:
        st.error("❌ Crawler found nothing. (Are the params exactly matching v801?)")

if st.button("🔴 Run Crawler"):
    run_crawler()
