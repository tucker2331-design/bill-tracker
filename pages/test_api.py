import streamlit as st
import requests
import json

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525

st.set_page_config(page_title="v1200 Payload Permutation", page_icon="🎲", layout="wide")
st.title("🎲 v1200: The 'Payload Permutation'")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_payload_test():
    url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDsAsync"
    st.subheader(f"Targeting: `{url}`")
    
    # --- PERMUTATION 1: PascalCase Keys (Standard .NET) ---
    p1 = {"LegislationIds": [HB1_ID], "SessionCode": SESSION_CODE}
    
    # --- PERMUTATION 2: Just the IDs (Wrapped) ---
    p2 = {"ids": [HB1_ID]}
    
    # --- PERMUTATION 3: PascalCase without Session ---
    p3 = {"LegislationIds": [HB1_ID]}
    
    tests = [
        ("PascalCase + Session", p1),
        ("Wrapped 'ids'", p2),
        ("PascalCase Only", p3)
    ]
    
    for label, payload in tests:
        st.write(f"🔫 Testing **{label}**...")
        try:
            r = session.post(url, headers=headers, json=payload, timeout=5)
            if r.status_code == 200:
                st.success(f"🎉 **HIT!** {label} worked!")
                st.json(r.json())
                return # Stop on success
            else:
                st.warning(f"❌ {label} Failed: {r.status_code}")
        except Exception as e:
            st.error(f"Error: {e}")

    # --- PERMUTATION 4: THE "BILL NUMBER" GUESS ---
    st.divider()
    st.subheader("Attempt 4: Guessing 'GetLegislationByBillNumberAsync'...")
    # The Version service had this. Maybe Main service does too?
    guess_url = f"{API_BASE}/Legislation/api/GetLegislationByBillNumberAsync"
    
    try:
        # Try GET params
        params = {"sessionCode": SESSION_CODE, "billNumber": "HB1"}
        r4 = session.get(guess_url, headers=headers, params=params, timeout=5)
        
        if r4.status_code == 200:
            st.success("🎉 **JACKPOT!** The endpoint exists on the Main Service too!")
            st.json(r4.json())
        else:
            st.error(f"❌ Guess Failed: {r4.status_code} (Endpoint might not exist)")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Permutations"):
    run_payload_test()
