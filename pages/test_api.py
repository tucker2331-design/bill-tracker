import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
SESSION_CODE = "20261"
HB1_ID = 98525

st.set_page_config(page_title="v1202 The Double Wrap", page_icon="🌯", layout="wide")
st.title("🌯 v1202: The 'Double Wrap' Theory")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_double_wrap():
    # The endpoint that gave us 204 (Valid but Empty)
    base_url = f"{API_BASE}/Legislation/api/GetLegislationByLegislationIDsAsync"
    
    st.subheader(f"Targeting: `{base_url}`")
    
    # --- SHOT A: HYBRID (Session in URL, List in Body) ---
    # Many APIs take context in URL and data in body
    params_a = {"sessionCode": SESSION_CODE}
    body_a = [HB1_ID]
    
    # --- SHOT B: HYBRID NAMED (Session in URL, Object in Body) ---
    params_b = {"sessionCode": SESSION_CODE}
    body_b = {"ids": [HB1_ID]}
    
    # --- SHOT C: KEY GUESSING (All in Body) ---
    # Maybe the key is "LegislationIdList" or "legislationIdList"?
    body_c = {"LegislationIdList": [HB1_ID], "SessionCode": SESSION_CODE}
    
    tests = [
        ("Shot A (Hybrid List)", params_a, body_a),
        ("Shot B (Hybrid Object)", params_b, body_b),
        ("Shot C (Key Guess)", {}, body_c)
    ]
    
    for label, p, b in tests:
        st.write(f"🔫 Testing **{label}**...")
        try:
            r = session.post(base_url, headers=headers, params=p, json=b, timeout=5)
            
            if r.status_code == 200:
                data = r.json()
                st.success(f"🎉 **VICTORY!** {label} worked!")
                
                # Unwrap and show
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
                    st.warning("⚠️ 200 OK (Empty List).")
                    
            elif r.status_code == 204:
                st.warning(f"⚪ {label} -> 204 No Content")
            else:
                st.error(f"❌ {label} Failed: {r.status_code}")
                
        except Exception as e:
            st.error(f"Error: {e}")

if st.button("🔴 Run Double Wrap"):
    run_double_wrap()
