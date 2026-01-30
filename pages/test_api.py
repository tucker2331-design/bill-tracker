import streamlit as st
import requests

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 

# Control Bill (2024 HB1)
CONTROL_SESSION = "20241"
CONTROL_BILL = "HB1"

st.set_page_config(page_title="v1700 Manual & Cheat Code", page_icon="📖", layout="wide")
st.title("📖 v1700: The 'Manual' & The 'Cheat Code'")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY,
    'Origin': 'https://lis.virginia.gov',
    'Referer': 'https://lis.virginia.gov/'
}

def run_manual_check():
    # --- STEP 1: THE CHEAT CODE (SWAGGER/DOCS) ---
    st.subheader("Step 1: Attempting to Download API Schema...")
    
    # Common locations for Swagger/OpenAPI specs
    swagger_urls = [
        f"{API_BASE}/swagger/docs/v1",
        f"{API_BASE}/swagger/v1/swagger.json",
        f"{API_BASE}/openapi.json",
        f"{API_BASE}/api/docs"
    ]
    
    found_schema = False
    
    for url in swagger_urls:
        try:
            r = session.get(url, headers=headers, timeout=2)
            if r.status_code == 200:
                st.success(f"🎉 **FOUND THE MANUAL!** ({url})")
                data = r.json()
                
                # Try to find the History Endpoint Definition
                paths = data.get("paths", {})
                hist_path = "/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
                
                if hist_path in paths:
                    st.info("💡 **History Endpoint Definition:**")
                    # Check POST parameters
                    post_op = paths[hist_path].get("post")
                    if post_op:
                        params = post_op.get("parameters", [])
                        st.json(params)
                        # Check body schema
                        if "requestBody" in post_op:
                             st.write("Request Body Schema:")
                             st.json(post_op["requestBody"])
                
                found_schema = True
                break
        except:
            pass
            
    if not found_schema:
        st.warning("⚠️ Could not auto-fetch Swagger JSON. (We rely on Step 2).")

    # --- STEP 2: THE ID SWEEP (2024 CONTROL) ---
    st.divider()
    st.subheader("Step 2: The ID Sweep (2024 HB1)")
    st.write("Fetching ALL versions of 2024 HB1 to find the 'Master' ID...")
    
    # 1. Get all versions
    ver_url = f"{API_BASE}/LegislationVersion/api/GetLegislationVersionByBillNumberAsync"
    try:
        r = session.get(ver_url, headers=headers, params={"sessionCode": CONTROL_SESSION, "billNumber": CONTROL_BILL}, timeout=5)
        if r.status_code == 200:
            versions = r.json()
            # Unwrap
            if isinstance(versions, dict): versions = versions.get("LegislationsVersion", [])
            elif isinstance(versions, list): versions = versions
            
            st.write(f"Found {len(versions)} versions of 2024 HB1.")
            
            # 2. Test History for EVERY ID
            hist_url = f"{API_BASE}/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
            
            for v in versions:
                l_id = v.get("LegislationID")
                desc = v.get("Description")
                
                # Test Payload (camelCase standard)
                payload = {"legislationId": l_id, "sessionCode": CONTROL_SESSION}
                
                try:
                    h_r = session.post(hist_url, headers=headers, json=payload, timeout=2)
                    
                    if h_r.status_code == 200:
                        h_data = h_r.json()
                        h_items = []
                        if isinstance(h_data, dict): h_items = h_data.get("LegislationHistory", [])
                        elif isinstance(h_data, list): h_items = h_data
                        
                        if h_items:
                            st.success(f"🎉 **JACKPOT!** ID `{l_id}` ({desc}) unlocked the History!")
                            st.dataframe(h_items)
                            
                            # CHECK FOR COMMITTEE
                            ref = next((x for x in h_items if "Referred" in str(x.get("Description"))), None)
                            if ref:
                                st.info(f"📍 **COMMITTEE:** {ref.get('Description')}")
                            return # Stop, we found the pattern
                        else:
                            st.caption(f"⚪ ID {l_id} ({desc}): Empty History")
                    else:
                        st.caption(f"❌ ID {l_id}: Status {h_r.status_code}")
                        
                except Exception:
                    pass
        else:
            st.error("❌ Failed to fetch versions.")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Run Manual & Sweep"):
    run_manual_check()
