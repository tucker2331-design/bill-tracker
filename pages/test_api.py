import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525

st.set_page_config(page_title="v1201 The 204 Breakthrough", page_icon="🔓", layout="wide")
st.title("🔓 v1201: The '204' Breakthrough")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_breakthrough():
    url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDsAsync"
    st.subheader(f"Targeting: `{url}`")
    
    # We proceed with variations of the structure that gave us 204 (Valid Request)
    
    # --- PAYLOAD 1: The Logical Fix (ids + sessionCode) ---
    p1 = {
        "ids": [HB1_ID], 
        "sessionCode": SESSION_CODE 
    }
    
    # --- PAYLOAD 2: CamelCase Correction (legislationIds + sessionCode) ---
    # .NET APIs usually prefer camelCase over PascalCase
    p2 = {
        "legislationIds": [HB1_ID],
        "sessionCode": SESSION_CODE
    }
    
    tests = [
        ("payload_1", p1, "ids + sessionCode"),
        ("payload_2", p2, "legislationIds + sessionCode")
    ]
    
    for key, payload, desc in tests:
        st.write(f"🔫 Testing **{desc}**...")
        try:
            r = session.post(url, headers=headers, json=payload, timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                st.success(f"🎉 **VICTORY!** {desc} worked!")
                
                # Show the Master Record
                items = []
                if isinstance(data, dict):
                    items = data.get("Legislation") or data.get("Items") or []
                elif isinstance(data, list):
                    items = data
                    
                if items:
                    master = items[0]
                    st.info(f"📍 **Committee:** {master.get('CommitteeName')} (ID: {master.get('CommitteeId')})")
                    st.json(master)
                    return
                else:
                    st.warning("⚠️ 200 OK (Empty List) - Payload accepted, but still no data found.")
                    st.json(data)
                    
            elif r.status_code == 204:
                st.warning(f"⚪ {desc} -> 204 No Content (Valid syntax, but API can't find ID {HB1_ID} in Session {SESSION_CODE}?)")
            else:
                st.error(f"❌ {desc} Failed: {r.status_code}")
                
        except Exception as e:
            st.error(f"Error: {e}")

if st.button("🔴 Run Breakthrough"):
    run_breakthrough()
