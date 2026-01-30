import streamlit as st
import requests
import json

# --- CONFIGURATION ---
API_BASE = "https://lis.virginia.gov"
API_KEY = "81D70A54-FCDC-4023-A00B-A3FD114D5984" 
CONTROL_ID = 91072 # 2024 HB1 (Known History)
CONTROL_SESSION = "20241"

st.set_page_config(page_title="v1800 Manual Extraction", page_icon="📜", layout="wide")
st.title("📜 v1800: The 'Manual' Extraction")

session = requests.Session()
headers = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'WebAPIKey': API_KEY
}

def run_extraction():
    # 1. FETCH THE MANUAL
    st.subheader("Step 1: Reading the Instructions...")
    
    # We use the URL that worked in v1700
    swagger_url = f"{API_BASE}/swagger/docs/v1"
    
    try:
        r = session.get(swagger_url, headers=headers, timeout=5)
        if r.status_code == 200:
            spec = r.json()
            st.success("✅ Downloaded API Definition!")
            
            # 2. HUNT FOR THE HISTORY ENDPOINT
            # We look for the path definition in the huge JSON
            target_path = "/Legislation/api/GetLegislationStatusHistoryByLegislationIDAsync"
            path_def = spec.get("paths", {}).get(target_path, {})
            
            if path_def:
                post_def = path_def.get("post", {})
                
                # EXTRACT PARAMETERS
                st.info("💡 **ENDPOINT REQUIREMENTS:**")
                
                # A. URL Parameters?
                params = post_def.get("parameters", [])
                if params:
                    st.write("### URL Parameters:")
                    st.json(params)
                else:
                    st.write("### No URL Parameters found.")

                # B. Body Schema?
                req_body = post_def.get("requestBody", {})
                content = req_body.get("content", {}).get("application/json", {})
                schema = content.get("schema", {})
                
                # If schema is a $ref, we need to look it up
                ref = schema.get("$ref")
                if ref:
                    # e.g., "#/components/schemas/LegislationHistoryRequest"
                    def_name = ref.split("/")[-1]
                    real_schema = spec.get("components", {}).get("schemas", {}).get(def_name, {})
                    st.write(f"### Body Schema ({def_name}):")
                    st.json(real_schema)
                    
                    # 3. LIVE FIRE TEST BASED ON FINDINGS
                    st.divider()
                    st.subheader("Step 2: Testing with EXACT Schema...")
                    
                    # Construct payload based on properties found
                    props = real_schema.get("properties", {})
                    payload = {}
                    
                    # Auto-fill known values
                    for key in props.keys():
                        lower_key = key.lower()
                        if "id" in lower_key and "session" not in lower_key:
                            payload[key] = CONTROL_ID
                        elif "session" in lower_key:
                            payload[key] = CONTROL_SESSION
                            
                    st.write("🚀 Constructed Payload from Schema:", payload)
                    
                    # FIRE!
                    url = f"{API_BASE}{target_path}"
                    r_test = session.post(url, headers=headers, json=payload, timeout=5)
                    
                    if r_test.status_code == 200:
                        st.success("🎉 **IT WORKED!** History Unlocked!")
                        st.dataframe(r_test.json())
                    elif r_test.status_code == 204:
                         st.warning("⚠️ Still 204 No Content (Maybe ID is wrong?)")
                    else:
                        st.error(f"❌ Failed: {r_test.status_code}")
                        
                else:
                    st.write("### Raw Schema (No Ref):")
                    st.json(schema)
            else:
                st.error("❌ Could not find History endpoint in Swagger.")
                st.write("Available Paths:", list(spec.get("paths", {}).keys())[:5])
        else:
            st.error(f"❌ Failed to download Manual: {r.status_code}")
            
    except Exception as e:
        st.error(f"Error: {e}")

if st.button("🔴 Read Manual"):
    run_extraction()
