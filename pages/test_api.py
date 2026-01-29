import streamlit as st
import requests
import traceback

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
DEFAULT_SESSION = "20261" 
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

st.set_page_config(page_title="v800 HB1 Rosetta Stone", page_icon="🗿", layout="wide")
st.title("🗿 v800: The 'HB1' Rosetta Stone")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_rosetta_stone():
    st.subheader("Step 1: Diagnosing the 'Session Check' Error...")
    
    # 1. Debugging the Session Endpoint
    s_url = f"{API_BASE}/Session/api/GetSessionListAsync"
    try:
        r = session.get(s_url, headers=headers, timeout=5)
        st.write(f"📡 Session Endpoint Status: `{r.status_code}`")
        if r.status_code == 200:
            st.success("✅ Session List Downloaded!")
            data = r.json()
            # Show the first session to verify format
            if isinstance(data, list) and data:
                st.json(data[0])
            elif isinstance(data, dict):
                st.json(data)
    except Exception:
        st.error("❌ Connection Failed. Traceback:")
        st.code(traceback.format_exc())

    # --- STEP 2: HUNTING FOR HB1 ---
    st.divider()
    st.subheader("Step 2: Hunting for Bill 'HB1'...")
    
    # We will try 3 different endpoints from your Heist list
    
    targets = [
        # Target A: LegislationVersion Service
        {
            "url": f"{API_BASE}/LegislationVersion/api/GetLegislationVersionByBillNumberAsync",
            "params": {"sessionCode": DEFAULT_SESSION, "billNumber": "HB1"},
            "method": "GET"
        },
        # Target B: Legislation Service (GetLegislationById is unlikely to take HB1, but maybe)
        # Better candidate: LegislationText
        {
            "url": f"{API_BASE}/LegislationText/api/GetLegislationTextByIDAsync",
            "params": {"sessionCode": DEFAULT_SESSION, "billNumber": "HB1"}, # Guessing param name
            "method": "GET"
        },
        # Target C: Advanced Search (POST) - Asking specifically for HB1
        {
            "url": f"{API_BASE}/AdvancedLegislationSearch/api/GetLegislationListAsync",
            "json": {
                "SessionCode": DEFAULT_SESSION,
                "BillNumber": "HB1", 
                "ChamberCode": "H"
            },
            "method": "POST"
        }
    ]
    
    for i, t in enumerate(targets):
        label = t['url'].split("/api/")[1]
        st.markdown(f"**🔫 Attempt {i+1}:** `{label}`")
        
        try:
            if t['method'] == "GET":
                resp = session.get(t['url'], headers=headers, params=t.get('params'), timeout=5)
            else:
                resp = session.post(t['url'], headers=headers, json=t.get('json'), timeout=5)
            
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    st.success(f"🎉 **ROSETTA STONE FOUND!** Data received from {label}")
                    st.json(data)
                    return # Stop if we find it
                else:
                    st.warning("⚠️ 200 OK (Empty Result)")
            elif resp.status_code == 204:
                st.caption("⚪ 204 No Content (Bill not found or params wrong)")
            else:
                st.error(f"❌ Status {resp.status_code}")
                
        except Exception as e:
            st.error(f"Error: {e}")

if st.button("🔴 Run Rosetta Stone"):
    run_rosetta_stone()
