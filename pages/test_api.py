import streamlit as st
import requests
import re
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
BASE_URL = "https://lis.virginia.gov"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

st.set_page_config(page_title="v304 Source Heist", page_icon="🥷", layout="wide")
st.title("🥷 v304: The Source Code Heist")
st.markdown("### 🎯 Goal: Extract valid API endpoints directly from the website's code.")

session = requests.Session()

def run_heist():
    # Step 1: Get the Homepage to find the latest JS file name
    st.write("📡 Scanning Homepage for JavaScript files...")
    try:
        resp = session.get(f"{BASE_URL}/session-details/20261/committee-information/H18/committee-details", headers=HEADERS, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        scripts = []
        for s in soup.find_all('script'):
            src = s.get('src')
            if src and "static/js/" in src:
                scripts.append(src)
        
        if not scripts:
            st.error("❌ No JS files found. The site might have changed structure.")
            return

        st.success(f"✅ Found {len(scripts)} scripts. Analyzing...")
        
        # Step 2: Download each JS file and hunt for API patterns
        found_endpoints = set()
        
        for script_url in scripts:
            full_url = f"{BASE_URL}{script_url}"
            st.text(f"Downloading: {script_url} ...")
            
            js_resp = session.get(full_url, headers=HEADERS, timeout=10)
            if js_resp.status_code == 200:
                content = js_resp.text
                
                # PATTERN: Look for anything that looks like an API call
                # e.g., "api/GetDocketList" or "CommitteeLegislation/api/"
                # Regex explanation:
                # [a-zA-Z0-9_/]+  -> Match words and slashes
                # /api/           -> Must contain "/api/"
                # [a-zA-Z0-9_]+   -> Followed by the endpoint name
                matches = re.findall(r'([a-zA-Z0-9_]+)/api/([a-zA-Z0-9_]+)', content)
                
                for service, action in matches:
                    endpoint = f"{service}/api/{action}"
                    found_endpoints.add(endpoint)
                    
        # Step 3: Display Results
        st.divider()
        if found_endpoints:
            st.success(f"🎉 SUCCESS! Stolen {len(found_endpoints)} API Endpoints:")
            
            # Sort them for readability
            sorted_eps = sorted(list(found_endpoints))
            
            # Group by Service
            grouped = {}
            for ep in sorted_eps:
                service, action = ep.split("/api/")
                if service not in grouped: grouped[service] = []
                grouped[service].append(action)
            
            for service, actions in grouped.items():
                with st.expander(f"📂 Service: {service} ({len(actions)})"):
                    for a in actions:
                        # Make them clickable test buttons? No, just list them for now.
                        st.code(f"{service}/api/{a}", language="text")
                        
            st.info("👇 Look closely at the list above. Do you see 'Docket', 'Agenda', or 'Legislation'?")
        else:
            st.warning("⚠️ Scanned code but found no '/api/' patterns. They might hide them differently.")

    except Exception as e:
        st.error(f"Heist Failed: {e}")

if st.button("🔴 Heist the Endpoints"):
    run_heist()
