import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# WE KNOW THIS BILL HAS HISTORY (2024 HB1)
CONTROL_ID = 91072 
CONTROL_SESSION = "20241"

# THE GOAL (2026 HB1)
TARGET_ID = 98525
TARGET_SESSION = "20261"

st.set_page_config(page_title="v1600 Calibration", page_icon="🎛️", layout="wide")
st.title("🎛️ v1600: The 'Control Bill' Calibration")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_calibration():
    url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
    st.subheader(f"Step 1: Brute-Forcing the Key on 2024 HB1...")
    
    # PERMUTATIONS TO TEST
    tests = [
        # 1. camelCase (Standard JSON)
        {"label": "camelCase", "payload": {"legislationId": CONTROL_ID, "sessionCode": CONTROL_SESSION}},
        
        # 2. PascalCase (Standard .NET)
        {"label": "PascalCase", "payload": {"LegislationId": CONTROL_ID, "SessionCode": CONTROL_SESSION}},
        
        # 3. ID Capitalized (Common LIS quirk)
        {"label": "ID Capitalized", "payload": {"LegislationID": CONTROL_ID, "SessionCode": CONTROL_SESSION}},
        
        # 4. No Session (Maybe ID is enough?)
        {"label": "ID Only", "payload": {"legislationId": CONTROL_ID}}
    ]
    
    winning_payload_type = None
    
    for t in tests:
        st.write(f"🔫 Testing **{t['label']}**...")
        try:
            r = session.post(url, headers=headers, json=t['payload'], timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                # Check if actually empty
                items = []
                if isinstance(data, dict): items = data.get("LegislationHistory") or data.get("Items") or []
                elif isinstance(data, list): items = data
                
                if items:
                    st.success(f"🎉 **WINNER FOUND:** {t['label']} worked!")
                    winning_payload_type = t['label']
                    st.json(items[:1]) # Show first item proof
                    break # Stop, we found the key
                else:
                    st.warning(f"⚠️ {t['label']}: 200 OK but Empty List")
            elif r.status_code == 204:
                st.warning(f"⚪ {t['label']}: 204 No Content")
            else:
                st.error(f"❌ {t['label']}: Status {r.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

    # --- STEP 2: APPLY TO 2026 ---
    if winning_payload_type:
        st.divider()
        st.subheader(f"Step 2: Applying '{winning_payload_type}' to 2026 HB1...")
        
        # Construct the 2026 payload based on the winner
        target_payload = {}
        if winning_payload_type == "camelCase":
            target_payload = {"legislationId": TARGET_ID, "sessionCode": TARGET_SESSION}
        elif winning_payload_type == "PascalCase":
            target_payload = {"LegislationId": TARGET_ID, "SessionCode": TARGET_SESSION}
        elif winning_payload_type == "ID Capitalized":
            target_payload = {"LegislationID": TARGET_ID, "SessionCode": TARGET_SESSION}
        elif winning_payload_type == "ID Only":
            target_payload = {"legislationId": TARGET_ID}
            
        st.write("🚀 Sending Payload:", target_payload)
        
        try:
            r2 = session.post(url, headers=headers, json=target_payload, timeout=5)
            if r2.status_code == 200:
                data2 = r2.json()
                items2 = []
                if isinstance(data2, dict): items2 = data2.get("LegislationHistory") or data2.get("Items") or []
                elif isinstance(data2, list): items2 = data2
                
                if items2:
                    st.success(f"🎉 **JACKPOT!** Found {len(items2)} history events for 2026!")
                    st.dataframe(items2)
                    
                    # HUNT FOR COMMITTEE
                    ref = next((x for x in items2 if "Referred" in str(x.get("Description"))), None)
                    if ref:
                        st.info(f"📍 **COMMITTEE:** {ref.get('Description')}")
                else:
                    st.warning("⚠️ 200 OK (Empty List). Code is correct, but 2026 history is truly empty.")
            else:
                st.error(f"❌ 2026 Fetch Failed: {r2.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.error("❌ All permutations failed on the Control Bill. The API requires a structure we haven't guessed yet.")

if st.button("🔴 Run Calibration"):
    run_calibration()
